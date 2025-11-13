#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Workflow Intelligence System
Advanced AI-powered workflow automation with intelligent service detection and optimization
"""

import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ServiceType(Enum):
    """Enhanced service types with intelligent categorization"""

    COMMUNICATION = "communication"
    STORAGE = "storage"
    PRODUCTIVITY = "productivity"
    DEVELOPMENT = "development"
    CUSTOMER_SUPPORT = "customer_support"
    ANALYTICS = "analytics"
    PROJECT_MANAGEMENT = "project_management"
    CRM = "crm"
    MARKETING = "marketing"
    FINANCE = "finance"


class WorkflowComplexity(Enum):
    """Workflow complexity levels"""

    SIMPLE = "simple"  # 1-2 services, linear flow
    MEDIUM = "medium"  # 3-4 services, conditional logic
    COMPLEX = "complex"  # 5+ services, parallel execution
    ADVANCED = "advanced"  # Multi-phase, AI-powered decisions


@dataclass
class ServiceMapping:
    """Enhanced service mapping with intelligent detection"""

    service_name: str
    service_type: ServiceType
    aliases: List[str]
    keywords: List[str]
    priority: int  # Higher priority = more likely to be detected
    capabilities: List[str]
    integration_level: str  # basic, standard, advanced


@dataclass
class DetectedService:
    """Enhanced service detection result"""

    service_name: str
    confidence: float
    context: str
    detected_keywords: List[str]
    suggested_actions: List[str]


@dataclass
class WorkflowPattern:
    """Intelligent workflow pattern recognition"""

    pattern_name: str
    description: str
    service_sequence: List[str]
    complexity: WorkflowComplexity
    success_rate: float
    optimization_suggestions: List[str]


class EnhancedWorkflowIntelligence:
    """
    AI-Powered Workflow Intelligence System
    Provides advanced service detection, workflow optimization, and intelligent automation
    """


class ContextAnalyzer:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.service_patterns = {
            "slack": ["slack", "message", "channel", "chat", "notification"],
            "github": [
                "github",
                "pr",
                "pull request",
                "repository",
                "commit",
                "issue",
            ],
            "asana": ["asana", "task", "project", "assign", "due date"],
            "gmail": [
                "gmail",
                "gmail email",
                "google mail",
                "email",
                "inbox",
                "send",
                "reply",
            ],
            "google_calendar": [
                "google calendar",
                "calendar",
                "event",
                "meeting",
                "schedule",
            ],
            "trello": ["trello", "card", "board", "list", "move"],
            "notion": ["notion", "page", "database", "block"],
            "linear": ["linear", "ticket", "issue", "project"],
            "outlook": ["outlook", "email", "calendar", "meeting"],
            "dropbox": ["dropbox", "file", "folder", "upload"],
            "stripe": ["stripe", "payment", "invoice", "customer", "stripe invoice"],
            "salesforce": [
                "salesforce",
                "crm",
                "lead",
                "opportunity",
                "salesforce opportunity",
            ],
            "zoom": ["zoom", "meeting", "video", "call", "zoom meeting"],
            "tableau": [
                "tableau",
                "dashboard",
                "report",
                "analytics",
                "tableau report",
            ],
            "box": ["box", "file", "folder", "storage"],
            "whatsapp": ["whatsapp", "message", "chat", "business", "whatsapp message"],
        }

        self.action_patterns = {
            "send": ["send", "post", "share", "notify"],
            "create": ["create", "make", "add", "new"],
            "update": ["update", "modify", "change", "edit"],
            "delete": ["delete", "remove", "cancel"],
            "get": ["get", "fetch", "retrieve", "find"],
            "move": ["move", "transfer", "shift"],
        }

    def filter_services_by_context(
        self, detected_services: List[DetectedService], user_input: str
    ) -> List[DetectedService]:
        """
        Filter services based on contextual relevance and eliminate false positives
        """
        input_lower = user_input.lower()
        filtered_services = []

        for service in detected_services:
            # Check if service keywords actually appear in context
            context_matches = self._check_context_relevance(service, input_lower)

            # Check for action-service compatibility
            action_compatible = self._check_action_compatibility(service, input_lower)

            # Only include services that are contextually relevant
            if context_matches and action_compatible:
                filtered_services.append(service)

        return filtered_services

    def _check_context_relevance(
        self, service: DetectedService, input_lower: str
    ) -> bool:
        """Check if service keywords are actually used in meaningful context"""
        service_patterns = self.service_patterns.get(service.service_name, [])

        # Check for exact service name matches
        if service.service_name in input_lower:
            return True

        # Check for pattern matches with context
        for pattern in service_patterns:
            if pattern in input_lower:
                # Additional context check - ensure it's not just a random occurrence
                words = input_lower.split()
                if pattern in words:
                    return True

        return False

    def _check_action_compatibility(
        self, service: DetectedService, input_lower: str
    ) -> bool:
        """Check if the detected action is compatible with the service"""
        # Extract action from input
        detected_action = None
        for action, patterns in self.action_patterns.items():
            for pattern in patterns:
                if pattern in input_lower:
                    detected_action = action
                    break
            if detected_action:
                break

        # If no specific action detected, assume compatibility
        if not detected_action:
            return True

        # Service-specific action compatibility checks
        incompatible_actions = self._get_incompatible_actions(service.service_name)
        return detected_action not in incompatible_actions

    def _get_incompatible_actions(self, service_name: str) -> List[str]:
        """Define actions that are incompatible with specific services"""
        incompatible_map = {
            "github": [
                "move",
                "delete",
            ],  # GitHub doesn't typically "move" or "delete" in workflow context
            "gmail": [
                "create",
                "move",
            ],  # Gmail doesn't "create" or "move" in typical workflow patterns
            "google_calendar": [
                "send",
                "delete",
            ],  # Calendar doesn't "send" or typically "delete" in workflows
        }
        return incompatible_map.get(service_name, [])


class WorkflowOptimizationEngine:
    """Simple workflow optimization engine for basic workflow processing"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def optimize_workflow(
        self,
        workflow_steps: List[Dict[str, Any]],
        detected_services: List[DetectedService],
        complexity: WorkflowComplexity,
    ) -> List[Dict[str, Any]]:
        """Apply basic optimizations to workflow steps"""
        optimized_steps = []

        for step in workflow_steps:
            # Apply basic optimizations
            optimized_step = step.copy()

            # Add optimization metadata
            optimized_step["optimized"] = True
            optimized_step["optimization_type"] = "basic"

            optimized_steps.append(optimized_step)

        return optimized_steps


class EnhancedWorkflowIntelligence:
    def __init__(self):
        self.service_mappings = self._initialize_service_mappings()
        self.workflow_patterns = self._initialize_workflow_patterns()
        self.context_analyzer = ContextAnalyzer()
        self.optimization_engine = WorkflowOptimizationEngine()

    def _initialize_service_mappings(self) -> List[ServiceMapping]:
        """Initialize comprehensive service mappings with enhanced detection"""
        return [
            # Communication Services
            ServiceMapping(
                service_name="gmail",
                service_type=ServiceType.COMMUNICATION,
                aliases=["google mail", "gmail", "email"],
                keywords=[
                    "email",
                    "inbox",
                    "message",
                    "send email",
                    "receive email",
                    "important email",
                ],
                priority=95,
                capabilities=[
                    "send_email",
                    "read_emails",
                    "search_emails",
                    "filter_emails",
                ],
                integration_level="advanced",
            ),
            ServiceMapping(
                service_name="slack",
                service_type=ServiceType.COMMUNICATION,
                aliases=["slack", "team chat", "channel"],
                keywords=[
                    "slack",
                    "notification",
                    "team",
                    "channel",
                    "message",
                    "direct message",
                ],
                priority=90,
                capabilities=[
                    "send_message",
                    "create_channel",
                    "search_messages",
                    "file_sharing",
                ],
                integration_level="advanced",
            ),
            ServiceMapping(
                service_name="outlook",
                service_type=ServiceType.COMMUNICATION,
                aliases=["microsoft outlook", "outlook", "office 365"],
                keywords=["outlook", "email", "calendar", "meeting", "office"],
                priority=85,
                capabilities=["send_email", "manage_calendar", "schedule_meetings"],
                integration_level="standard",
            ),
            # Productivity Services
            ServiceMapping(
                service_name="asana",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["asana", "task management", "project"],
                keywords=[
                    "asana",
                    "task",
                    "project",
                    "assign",
                    "due date",
                    "complete task",
                ],
                priority=90,
                capabilities=[
                    "create_task",
                    "update_task",
                    "assign_task",
                    "set_due_date",
                ],
                integration_level="advanced",
            ),
            ServiceMapping(
                service_name="trello",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["trello", "board", "card"],
                keywords=["trello", "board", "card", "list", "move card", "assign"],
                priority=85,
                capabilities=[
                    "create_card",
                    "move_card",
                    "assign_member",
                    "add_comment",
                ],
                integration_level="standard",
            ),
            ServiceMapping(
                service_name="notion",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["notion", "notes", "database"],
                keywords=["notion", "page", "database", "note", "document"],
                priority=80,
                capabilities=[
                    "create_page",
                    "update_page",
                    "search_pages",
                    "create_database",
                ],
                integration_level="standard",
            ),
            # Storage Services
            ServiceMapping(
                service_name="google_drive",
                service_type=ServiceType.STORAGE,
                aliases=["google drive", "gdrive", "drive"],
                keywords=[
                    "google drive",
                    "drive",
                    "document",
                    "file",
                    "folder",
                    "share",
                ],
                priority=85,
                capabilities=[
                    "upload_file",
                    "share_file",
                    "search_files",
                    "create_folder",
                ],
                integration_level="advanced",
            ),
            ServiceMapping(
                service_name="dropbox",
                service_type=ServiceType.STORAGE,
                aliases=["dropbox", "file storage"],
                keywords=["dropbox", "file", "upload", "share", "sync"],
                priority=80,
                capabilities=["upload_file", "share_link", "sync_files"],
                integration_level="standard",
            ),
            # Calendar Services
            ServiceMapping(
                service_name="google_calendar",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["google calendar", "gcal", "calendar"],
                keywords=[
                    "calendar",
                    "meeting",
                    "schedule",
                    "event",
                    "appointment",
                    "reminder",
                ],
                priority=90,
                capabilities=[
                    "create_event",
                    "find_availability",
                    "send_invites",
                    "set_reminders",
                ],
                integration_level="advanced",
            ),
            # Development Services
            ServiceMapping(
                service_name="github",
                service_type=ServiceType.DEVELOPMENT,
                aliases=["github", "git", "repository"],
                keywords=[
                    "github",
                    "repository",
                    "issue",
                    "pull request",
                    "commit",
                    "code",
                ],
                priority=85,
                capabilities=[
                    "create_issue",
                    "create_pr",
                    "search_repos",
                    "manage_projects",
                ],
                integration_level="advanced",
            ),
            ServiceMapping(
                service_name="gitlab",
                service_type=ServiceType.DEVELOPMENT,
                aliases=["gitlab", "ci/cd", "repository"],
                keywords=["gitlab", "pipeline", "merge request", "repository"],
                priority=80,
                capabilities=["create_issue", "run_pipeline", "merge_requests"],
                integration_level="standard",
            ),
            # CRM Services
            ServiceMapping(
                service_name="salesforce",
                service_type=ServiceType.CRM,
                aliases=["salesforce", "crm", "sales"],
                keywords=["salesforce", "lead", "opportunity", "account", "contact"],
                priority=85,
                capabilities=["create_lead", "update_contact", "create_opportunity"],
                integration_level="advanced",
            ),
            ServiceMapping(
                service_name="hubspot",
                service_type=ServiceType.CRM,
                aliases=["hubspot", "marketing", "crm"],
                keywords=["hubspot", "contact", "deal", "pipeline", "marketing"],
                priority=80,
                capabilities=["create_contact", "update_deal", "send_email"],
                integration_level="standard",
            ),
            # Payment Services
            ServiceMapping(
                service_name="stripe",
                service_type=ServiceType.FINANCE,
                aliases=["stripe", "payment", "billing"],
                keywords=["stripe", "payment", "invoice", "customer", "stripe invoice"],
                priority=80,
                capabilities=["create_invoice", "process_payment", "manage_customers"],
                integration_level="standard",
            ),
            # Communication Services
            ServiceMapping(
                service_name="zoom",
                service_type=ServiceType.COMMUNICATION,
                aliases=["zoom", "video", "meeting"],
                keywords=["zoom", "meeting", "video", "call", "zoom meeting"],
                priority=75,
                capabilities=["schedule_meeting", "join_meeting", "record_meeting"],
                integration_level="standard",
            ),
            # Analytics Services
            ServiceMapping(
                service_name="tableau",
                service_type=ServiceType.ANALYTICS,
                aliases=["tableau", "dashboard", "reporting"],
                keywords=[
                    "tableau",
                    "dashboard",
                    "report",
                    "analytics",
                    "tableau report",
                ],
                priority=75,
                capabilities=["create_dashboard", "generate_report", "analyze_data"],
                integration_level="standard",
            ),
            # Business Communication Services
            ServiceMapping(
                service_name="whatsapp",
                service_type=ServiceType.COMMUNICATION,
                aliases=["whatsapp", "whatsapp business", "messaging"],
                keywords=[
                    "whatsapp",
                    "message",
                    "chat",
                    "business",
                    "whatsapp message",
                ],
                priority=70,
                capabilities=["send_message", "receive_message", "business_messaging"],
                integration_level="basic",
            ),
        ]

    def _initialize_workflow_patterns(self) -> List[WorkflowPattern]:
        """Initialize intelligent workflow patterns for optimization"""
        return [
            WorkflowPattern(
                pattern_name="Email to Task Automation",
                description="Convert emails to tasks with intelligent prioritization",
                service_sequence=["gmail", "asana", "slack"],
                complexity=WorkflowComplexity.MEDIUM,
                success_rate=0.92,
                optimization_suggestions=[
                    "Use AI to prioritize tasks based on email content",
                    "Automatically categorize tasks by project",
                    "Set intelligent due dates based on email urgency",
                ],
            ),
            WorkflowPattern(
                pattern_name="Meeting Follow-up Workflow",
                description="Automated meeting follow-ups with task creation",
                service_sequence=["google_calendar", "asana", "gmail"],
                complexity=WorkflowComplexity.MEDIUM,
                success_rate=0.88,
                optimization_suggestions=[
                    "Extract action items from meeting notes automatically",
                    "Assign tasks based on meeting participants",
                    "Schedule follow-up reminders",
                ],
            ),
            WorkflowPattern(
                pattern_name="Multi-Service Document Processing",
                description="Intelligent document processing across services",
                service_sequence=["dropbox", "google_drive", "slack"],
                complexity=WorkflowComplexity.COMPLEX,
                success_rate=0.85,
                optimization_suggestions=[
                    "Use AI to categorize documents automatically",
                    "Optimize file transfer between services",
                    "Notify relevant teams based on document type",
                ],
            ),
            WorkflowPattern(
                pattern_name="Customer Support Automation",
                description="Automated customer support workflows",
                service_sequence=["gmail", "salesforce", "slack"],
                complexity=WorkflowComplexity.ADVANCED,
                success_rate=0.90,
                optimization_suggestions=[
                    "Use AI to triage support requests",
                    "Automatically route to appropriate teams",
                    "Generate response templates based on issue type",
                ],
            ),
        ]

    def detect_services_intelligently(self, user_input: str) -> List[DetectedService]:
        """
        Enhanced service detection with AI-powered intelligence
        """
        logger.info(f"Analyzing user input for service detection: {user_input}")

        detected_services = []
        input_lower = user_input.lower()

        for service_mapping in self.service_mappings:
            confidence = self._calculate_service_confidence(
                service_mapping, input_lower, user_input
            )

            if confidence > 0.2:  # Lower threshold to capture more potential matches
                detected_keywords = self._extract_matching_keywords(
                    service_mapping, input_lower
                )

                suggested_actions = self._generate_suggested_actions(
                    service_mapping, input_lower
                )

                detected_service = DetectedService(
                    service_name=service_mapping.service_name,
                    confidence=confidence,
                    context=self._analyze_service_context(service_mapping, user_input),
                    detected_keywords=detected_keywords,
                    suggested_actions=suggested_actions,
                )

                detected_services.append(detected_service)

        # Sort by confidence and priority
        detected_services.sort(
            key=lambda x: (x.confidence, self._get_service_priority(x.service_name)),
            reverse=True,
        )

        # Apply context-based filtering
        filtered_services = self.context_analyzer.filter_services_by_context(
            detected_services, user_input
        )

        logger.info(
            f"Detected {len(filtered_services)} services with enhanced intelligence"
        )
        return filtered_services

    def _calculate_service_confidence(
        self, service_mapping: ServiceMapping, input_lower: str, original_input: str
    ) -> float:
        """Calculate confidence score for service detection"""
        confidence = 0.0

        # Keyword matching
        keyword_matches = 0
        for keyword in service_mapping.keywords:
            if keyword in input_lower:
                keyword_matches += 1
                confidence += 0.15  # Base keyword match

        # Alias matching
        for alias in service_mapping.aliases:
            if alias in input_lower:
                confidence += 0.25  # Higher weight for direct aliases

        # Context analysis
        context_score = self.context_analyzer._check_context_relevance(
            DetectedService(
                service_name=service_mapping.service_name,
                confidence=0.0,
                context={},
                detected_keywords=[],
                suggested_actions=[],
            ),
            original_input.lower(),
        )
        confidence += (1.0 if context_score else 0.0) * 0.3

        # Capability matching
        capability_score = self._analyze_capability_match(
            service_mapping, original_input
        )
        confidence += capability_score * 0.2

        # Apply priority multiplier
        confidence *= service_mapping.priority / 100.0

        return min(confidence, 1.0)  # Cap at 1.0

    def _extract_matching_keywords(
        self, service_mapping: ServiceMapping, input_lower: str
    ) -> List[str]:
        """Extract keywords that matched for this service"""
        matching_keywords = []
        for keyword in service_mapping.keywords:
            if keyword in input_lower:
                matching_keywords.append(keyword)
        return matching_keywords

    def _generate_suggested_actions(
        self, service_mapping: ServiceMapping, input_lower: str
    ) -> List[str]:
        """Generate intelligent action suggestions based on service and context"""
        actions = []

        # Base actions based on service type
        if service_mapping.service_type == ServiceType.COMMUNICATION:
            if "send" in input_lower or "notify" in input_lower:
                actions.append(f"Send message via {service_mapping.service_name}")
            if "receive" in input_lower or "check" in input_lower:
                actions.append(
                    f"Monitor {service_mapping.service_name} for new messages"
                )

        elif service_mapping.service_type == ServiceType.PRODUCTIVITY:
            if "create" in input_lower or "add" in input_lower:
                actions.append(f"Create item in {service_mapping.service_name}")
            if "update" in input_lower or "modify" in input_lower:
                actions.append(
                    f"Update existing item in {service_mapping.service_name}"
                )

        elif service_mapping.service_type == ServiceType.STORAGE:
            if "upload" in input_lower or "save" in input_lower:
                actions.append(f"Upload file to {service_mapping.service_name}")
            if "share" in input_lower or "send" in input_lower:
                actions.append(f"Share file from {service_mapping.service_name}")

        # Add capability-based actions
        for capability in service_mapping.capabilities:
            if any(
                action_word in input_lower for action_word in ["create", "make", "add"]
            ):
                if "create" in capability:
                    actions.append(
                        f"Use {service_mapping.service_name} to {capability}"
                    )

        return actions[:3]  # Limit to top 3 suggestions

    def _analyze_service_context(
        self, service_mapping: ServiceMapping, user_input: str
    ) -> str:
        """Analyze the context in which the service is being used"""
        context_indicators = {
            "urgent": ["urgent", "important", "critical", "asap"],
            "routine": ["daily", "weekly", "regular", "automatically"],
            "collaborative": ["team", "collaborate", "share", "together"],
            "monitoring": ["monitor", "watch", "track", "alert"],
        }

        input_lower = user_input.lower()
        contexts = []

        for context, indicators in context_indicators.items():
            if any(indicator in input_lower for indicator in indicators):
                contexts.append(context)

        return ", ".join(contexts) if contexts else "general"

    def _analyze_capability_match(
        self, service_mapping: ServiceMapping, user_input: str
    ) -> float:
        """Analyze how well service capabilities match user requirements"""
        capability_indicators = {
            "send_email": ["send email", "email someone", "notify via email"],
            "create_task": ["create task", "add todo", "make task"],
            "upload_file": ["upload file", "save document", "store file"],
            "schedule_meeting": ["schedule meeting", "set up call", "plan event"],
        }

        input_lower = user_input.lower()
        matches = 0
        total_capabilities = len(service_mapping.capabilities)

        if total_capabilities == 0:
            return 0.0

        for capability in service_mapping.capabilities:
            if capability in capability_indicators:
                indicators = capability_indicators[capability]
                if any(indicator in input_lower for indicator in indicators):
                    matches += 1

        return matches / total_capabilities

    def _get_service_priority(self, service_name: str) -> int:
        """Get priority for a service by name"""
        for mapping in self.service_mappings:
            if mapping.service_name == service_name:
                return mapping.priority
        return 50  # Default priority

    def generate_optimized_workflow(
        self, user_input: str, detected_services: List[DetectedService]
    ) -> Dict[str, Any]:
        """
        Generate optimized workflow with AI-powered intelligence
        """
        logger.info("Generating optimized workflow with enhanced intelligence")

        # Analyze workflow complexity
        complexity = self._analyze_workflow_complexity(detected_services, user_input)

        # Find matching patterns
        matching_patterns = self._find_matching_patterns(detected_services)

        # Generate workflow steps
        workflow_steps = self._generate_intelligent_steps(
            detected_services, user_input, complexity
        )

        # Apply optimizations
        optimized_workflow = self.optimization_engine.optimize_workflow(
            workflow_steps, detected_services, complexity
        )

        # Calculate confidence score
        confidence_score = self._calculate_workflow_confidence(
            detected_services, matching_patterns, complexity
        )

        workflow_data = {
            "workflow_id": str(uuid.uuid4()),
            "name": self._generate_workflow_name(user_input, detected_services),
            "description": user_input,
            "services": [service.service_name for service in detected_services],
            "complexity": complexity.value,
            "estimated_time": self._estimate_execution_time(
                detected_services, complexity
            ),
            "estimated_cost": self._estimate_execution_cost(
                detected_services, complexity
            ),
            "optimization_potential": confidence_score,
            "steps": optimized_workflow,
            "confidence": confidence_score,
            "created_at": datetime.now().isoformat(),
            "pattern_matches": [pattern.pattern_name for pattern in matching_patterns],
        }

        logger.info(
            f"Generated optimized workflow with {len(detected_services)} services"
        )
        return workflow_data

    def _generate_workflow_name(
        self, user_input: str, detected_services: List[DetectedService]
    ) -> str:
        """Generate intelligent workflow name based on services and input"""
        service_names = [service.service_name for service in detected_services]
        if len(service_names) == 1:
            return f"{service_names[0].title()} Automation"
        elif len(service_names) == 2:
            return f"{service_names[0].title()} to {service_names[1].title()} Workflow"
        else:
            return f"Multi-Service {len(service_names)} Integration"

    def _analyze_workflow_complexity(
        self, detected_services: List[DetectedService], user_input: str
    ) -> WorkflowComplexity:
        """Analyze workflow complexity based on services and context"""
        service_count = len(detected_services)

        if service_count == 1:
            return WorkflowComplexity.SIMPLE
        elif service_count == 2:
            return WorkflowComplexity.MEDIUM
        elif service_count == 3:
            return WorkflowComplexity.COMPLEX
        else:
            return WorkflowComplexity.ADVANCED

    def _find_matching_patterns(
        self, detected_services: List[DetectedService]
    ) -> List[WorkflowPattern]:
        """Find matching workflow patterns for optimization"""
        service_names = [service.service_name for service in detected_services]
        matching_patterns = []

        for pattern in self.workflow_patterns:
            if all(service in service_names for service in pattern.service_sequence):
                matching_patterns.append(pattern)

        return matching_patterns

    def _generate_intelligent_steps(
        self,
        detected_services: List[DetectedService],
        user_input: str,
        complexity: WorkflowComplexity,
    ) -> List[Dict[str, Any]]:
        """Generate intelligent workflow steps based on detected services"""
        steps = []

        for i, service in enumerate(detected_services):
            step = {
                "step_id": i + 1,
                "service": service.service_name,
                "action": self._determine_service_action(service, user_input),
                "parameters": self._extract_service_parameters(service, user_input),
                "depends_on": [] if i == 0 else [i],  # Sequential dependency
                "estimated_duration": 30,  # Default duration in seconds
            }
            steps.append(step)

        return steps

    def _determine_service_action(
        self, service: DetectedService, user_input: str
    ) -> str:
        """Determine the most likely action for a service based on context"""
        input_lower = user_input.lower()

        action_mapping = {
            "slack": "send_message"
            if any(word in input_lower for word in ["send", "notify", "message"])
            else "get_messages",
            "github": "create_pr"
            if "pr" in input_lower or "pull request" in input_lower
            else "get_repositories",
            "asana": "create_task"
            if any(word in input_lower for word in ["create", "add", "make"])
            else "get_tasks",
            "gmail": "send_email" if "send" in input_lower else "get_emails",
            "google_calendar": "create_event"
            if any(word in input_lower for word in ["schedule", "create", "add"])
            else "get_events",
        }

        return action_mapping.get(service.service_name, "execute")

    def _extract_service_parameters(
        self, service: DetectedService, user_input: str
    ) -> Dict[str, Any]:
        """Extract relevant parameters for service actions"""
        parameters = {}
        input_lower = user_input.lower()

        # Extract common parameters based on service type
        if service.service_name == "slack":
            if "channel" in input_lower:
                parameters["channel"] = "general"  # Default channel
            parameters["message"] = "Automated message from workflow"

        elif service.service_name == "asana":
            parameters["task_name"] = "Automated task"
            if "project" in input_lower:
                parameters["project"] = "Default Project"

        elif service.service_name == "gmail":
            parameters["subject"] = "Automated email"
            parameters["body"] = "This is an automated email from your workflow"

        return parameters

    def _estimate_execution_time(
        self, detected_services: List[DetectedService], complexity: WorkflowComplexity
    ) -> float:
        """Estimate workflow execution time based on complexity"""
        base_time = len(detected_services) * 30  # 30 seconds per service
        complexity_multiplier = {
            WorkflowComplexity.SIMPLE: 1.0,
            WorkflowComplexity.MEDIUM: 1.5,
            WorkflowComplexity.COMPLEX: 2.0,
            WorkflowComplexity.ADVANCED: 3.0,
        }

        return base_time * complexity_multiplier.get(complexity, 1.0)

    def _estimate_execution_cost(
        self, detected_services: List[DetectedService], complexity: WorkflowComplexity
    ) -> float:
        """Estimate workflow execution cost based on services and complexity"""
        base_cost = len(detected_services) * 0.05  # $0.05 per service call
        complexity_multiplier = {
            WorkflowComplexity.SIMPLE: 1.0,
            WorkflowComplexity.MEDIUM: 1.2,
            WorkflowComplexity.COMPLEX: 1.5,
            WorkflowComplexity.ADVANCED: 2.0,
        }

        return base_cost * complexity_multiplier.get(complexity, 1.0)

    def _calculate_workflow_confidence(
        self,
        detected_services: List[DetectedService],
        matching_patterns: List[WorkflowPattern],
        complexity: WorkflowComplexity,
    ) -> float:
        """Calculate overall confidence score for the generated workflow"""
        # Base confidence from service detection
        service_confidence = (
            sum(service.confidence for service in detected_services)
            / len(detected_services)
            if detected_services
            else 0.0
        )

        # Pattern matching bonus
        pattern_bonus = 0.1 * len(matching_patterns)

        # Complexity adjustment (simpler workflows are more reliable)
        complexity_penalty = {
            WorkflowComplexity.SIMPLE: 0.0,
            WorkflowComplexity.MEDIUM: -0.05,
            WorkflowComplexity.COMPLEX: -0.1,
            WorkflowComplexity.ADVANCED: -0.2,
        }

        final_confidence = (
            service_confidence + pattern_bonus + complexity_penalty.get(complexity, 0.0)
        )
        return max(0.0, min(1.0, final_confidence))


# Initialize the enhanced workflow intelligence system
enhanced_intelligence = EnhancedWorkflowIntelligence()
