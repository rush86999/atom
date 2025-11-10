#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Enhanced Workflow Intelligence System
Advanced AI-powered workflow automation with intelligent service detection and optimization
"""

import json
import re
import logging
import asyncio
from typing import Dict, List, Any, Optional, Tuple
from dataclasses import dataclass
from enum import Enum
import uuid
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
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
                keywords=["email", "inbox", "message", "send email", "receive email", "important email"],
                priority=95,
                capabilities=["send_email", "read_emails", "search_emails", "filter_emails"],
                integration_level="advanced"
            ),
            ServiceMapping(
                service_name="slack",
                service_type=ServiceType.COMMUNICATION,
                aliases=["slack", "team chat", "channel"],
                keywords=["slack", "notification", "team", "channel", "message", "direct message"],
                priority=90,
                capabilities=["send_message", "create_channel", "search_messages", "file_sharing"],
                integration_level="advanced"
            ),
            ServiceMapping(
                service_name="outlook",
                service_type=ServiceType.COMMUNICATION,
                aliases=["microsoft outlook", "outlook", "office 365"],
                keywords=["outlook", "email", "calendar", "meeting", "office"],
                priority=85,
                capabilities=["send_email", "manage_calendar", "schedule_meetings"],
                integration_level="standard"
            ),

            # Productivity Services
            ServiceMapping(
                service_name="asana",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["asana", "task management", "project"],
                keywords=["asana", "task", "project", "assign", "due date", "complete task"],
                priority=90,
                capabilities=["create_task", "update_task", "assign_task", "set_due_date"],
                integration_level="advanced"
            ),
            ServiceMapping(
                service_name="trello",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["trello", "board", "card"],
                keywords=["trello", "board", "card", "list", "move card", "assign"],
                priority=85,
                capabilities=["create_card", "move_card", "assign_member", "add_comment"],
                integration_level="standard"
            ),
            ServiceMapping(
                service_name="notion",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["notion", "notes", "database"],
                keywords=["notion", "page", "database", "note", "document"],
                priority=80,
                capabilities=["create_page", "update_page", "search_pages", "create_database"],
                integration_level="standard"
            ),

            # Storage Services
            ServiceMapping(
                service_name="google_drive",
                service_type=ServiceType.STORAGE,
                aliases=["google drive", "gdrive", "drive"],
                keywords=["google drive", "drive", "document", "file", "folder", "share"],
                priority=85,
                capabilities=["upload_file", "share_file", "search_files", "create_folder"],
                integration_level="advanced"
            ),
            ServiceMapping(
                service_name="dropbox",
                service_type=ServiceType.STORAGE,
                aliases=["dropbox", "file storage"],
                keywords=["dropbox", "file", "upload", "share", "sync"],
                priority=80,
                capabilities=["upload_file", "share_link", "sync_files"],
                integration_level="standard"
            ),

            # Calendar Services
            ServiceMapping(
                service_name="google_calendar",
                service_type=ServiceType.PRODUCTIVITY,
                aliases=["google calendar", "gcal", "calendar"],
                keywords=["calendar", "meeting", "schedule", "event", "appointment", "reminder"],
                priority=90,
                capabilities=["create_event", "find_availability", "send_invites", "set_reminders"],
                integration_level="advanced"
            ),

            # Development Services
            ServiceMapping(
                service_name="github",
                service_type=ServiceType.DEVELOPMENT,
                aliases=["github", "git", "repository"],
                keywords=["github", "repository", "issue", "pull request", "commit", "code"],
                priority=85,
                capabilities=["create_issue", "create_pr", "search_repos", "manage_projects"],
                integration_level="advanced"
            ),
            ServiceMapping(
                service_name="gitlab",
                service_type=ServiceType.DEVELOPMENT,
                aliases=["gitlab", "ci/cd", "repository"],
                keywords=["gitlab", "pipeline", "merge request", "repository"],
                priority=80,
                capabilities=["create_issue", "run_pipeline", "merge_requests"],
                integration_level="standard"
            ),

            # CRM Services
            ServiceMapping(
                service_name="salesforce",
                service_type=ServiceType.CRM,
                aliases=["salesforce", "crm", "sales"],
                keywords=["salesforce", "lead", "opportunity", "account", "contact"],
                priority=85,
                capabilities=["create_lead", "update_contact", "create_opportunity"],
                integration_level="advanced"
            ),
            ServiceMapping(
                service_name="hubspot",
                service_type=ServiceType.CRM,
                aliases=["hubspot", "marketing", "crm"],
                keywords=["hubspot", "contact", "deal", "pipeline", "marketing"],
                priority=80,
                capabilities=["create_contact", "update_deal", "send_email"],
                integration_level="standard"
            )
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
                    "Set intelligent due dates based on email urgency"
                ]
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
                    "Schedule follow-up reminders"
                ]
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
                    "Notify relevant teams based on document type"
                ]
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
                    "Generate response templates based on issue type"
                ]
            )
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

            if confidence > 0.3:  # Threshold for detection
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
                    suggested_actions=suggested_actions
                )

                detected_services.append(detected_service)

        # Sort by confidence and priority
        detected_services.sort(key=lambda x: (x.confidence, self._get_service_priority(x.service_name)), reverse=True)

        # Apply context-based filtering
        filtered_services = self.context_analyzer.filter_services_by_context(
            detected_services, user_input
        )

        logger.info(f"Detected {len(filtered_services)} services with enhanced intelligence")
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
        context_score = self.context_analyzer.analyze_service_context(
            service_mapping.service_name, original_input
        )
        confidence += context_score * 0.3

        # Capability matching
        capability_score = self._analyze_capability_match(service_mapping, original_input)
        confidence += capability_score * 0.2

        # Apply priority multiplier
        confidence *= (service_mapping.priority / 100.0)

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
                actions.append(f"Monitor {service_mapping.service_name} for new messages")

        elif service_mapping.service_type == ServiceType.PRODUCTIVITY:
            if "create" in input_lower or "add" in input_lower:
                actions.append(f"Create item in {service_mapping.service_name}")
            if "update" in input_lower or "modify" in input_lower:
                actions.append(f"Update existing item in {service_mapping.service_name}")

        elif service_mapping.service_type == ServiceType.STORAGE:
            if "upload" in input_lower or "save" in input_lower:
                actions.append(f"Upload file to {service_mapping.service_name}")
            if "share" in input_lower or "send" in input_lower:
                actions.append(f"Share file from {service_mapping.service_name}")

        # Add capability-based actions
        for capability in service_mapping.capabilities:
            if any(action_word in input_lower for action_word in ["create", "make", "add"]):
                if "create" in capability:
                    actions.append(f"Use {service_mapping.service_name} to {capability}")

        return actions[:3]  # Limit to top 3 suggestions

    def _analyze_service_context(self, service_mapping: ServiceMapping, user_input: str) -> str:
        """Analyze the context in which the service is being used"""
        context_indicators = {
            "urgent": ["urgent", "important", "critical", "asap"],
            "routine": ["daily", "weekly", "regular", "automatically"],
            "collaborative": ["team", "collaborate", "share", "together"],
            "monitoring": ["monitor", "watch", "track", "alert"]
        }

        input_lower = user_input.lower()
        contexts = []

        for context, indicators in context_indicators.items():
            if any(indicator in input_lower for indicator in indicators):
                contexts.append(context)

        return ", ".join(contexts) if contexts else "general"

    def _analyze_capability_match(self, service_mapping: ServiceMapping, user_input: str) -> float:
        """Analyze how well service capabilities match user requirements"""
        capability_indicators = {
            "send_email": ["send email", "email someone", "notify via email"],
            "create_task": ["create task", "add todo", "make task"],
            "upload_file": ["upload file", "save document", "store file"],
            "schedule_meeting": ["schedule meeting", "set up call", "plan event"]
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
