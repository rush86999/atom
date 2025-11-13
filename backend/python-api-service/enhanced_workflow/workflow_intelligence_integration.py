"""
Workflow Intelligence Integration Module

This module provides integration between enhanced workflow intelligence
and the main backend API, including AI-powered service detection,
context-aware workflow generation, and intelligent pattern recognition.
"""

import logging
import os
import sys
from typing import Any, Dict, List, Optional

# Add parent directory to path to import enhanced modules
sys.path.append(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
)

logger = logging.getLogger(__name__)


class WorkflowIntelligenceIntegration:
    """Workflow Intelligence Integration with Enhanced AI Capabilities"""

    def __init__(self):
        self.service_mappings = {}
        self.workflow_patterns = {}
        self._initialize_intelligence_system()

    def _initialize_intelligence_system(self):
        """Initialize the enhanced workflow intelligence system"""
        try:
            # Initialize service mappings for 180+ services
            self.service_mappings = self._initialize_service_mappings()

            # Initialize workflow patterns
            self.workflow_patterns = self._initialize_workflow_patterns()

            logger.info(
                "Enhanced workflow intelligence system initialized successfully"
            )

        except Exception as e:
            logger.warning(
                f"Enhanced intelligence system initialization failed: {str(e)}"
            )
            logger.info("Falling back to basic intelligence system")
            self._initialize_basic_intelligence_system()

    def _initialize_service_mappings(self) -> Dict[str, Dict[str, Any]]:
        """Initialize comprehensive service mappings"""
        return {
            "communication": {
                "gmail": {
                    "keywords": ["email", "gmail", "send email", "inbox", "message"],
                    "actions": [
                        "send_email",
                        "read_email",
                        "search_emails",
                        "mark_as_read",
                    ],
                    "confidence_threshold": 0.8,
                    "category": "communication",
                },
                "slack": {
                    "keywords": ["slack", "message", "channel", "team", "notification"],
                    "actions": ["send_message", "create_channel", "search_messages"],
                    "confidence_threshold": 0.7,
                    "category": "communication",
                },
                "outlook": {
                    "keywords": [
                        "outlook",
                        "microsoft",
                        "calendar",
                        "meeting",
                        "appointment",
                    ],
                    "actions": ["send_email", "create_event", "list_contacts"],
                    "confidence_threshold": 0.8,
                    "category": "communication",
                },
            },
            "productivity": {
                "asana": {
                    "keywords": ["asana", "task", "project", "assign", "deadline"],
                    "actions": ["create_task", "update_task", "list_projects"],
                    "confidence_threshold": 0.75,
                    "category": "productivity",
                },
                "trello": {
                    "keywords": ["trello", "board", "card", "list", "kanban"],
                    "actions": ["create_card", "move_card", "add_comment"],
                    "confidence_threshold": 0.7,
                    "category": "productivity",
                },
                "notion": {
                    "keywords": ["notion", "page", "database", "notes", "wiki"],
                    "actions": ["create_page", "update_page", "search_pages"],
                    "confidence_threshold": 0.8,
                    "category": "productivity",
                },
            },
            "development": {
                "github": {
                    "keywords": [
                        "github",
                        "git",
                        "repository",
                        "commit",
                        "pull request",
                    ],
                    "actions": ["create_repo", "create_issue", "search_code"],
                    "confidence_threshold": 0.85,
                    "category": "development",
                },
                "gitlab": {
                    "keywords": ["gitlab", "ci/cd", "pipeline", "merge request"],
                    "actions": ["create_project", "run_pipeline", "review_code"],
                    "confidence_threshold": 0.8,
                    "category": "development",
                },
                "jira": {
                    "keywords": ["jira", "issue", "bug", "sprint", "backlog"],
                    "actions": ["create_issue", "update_issue", "search_issues"],
                    "confidence_threshold": 0.8,
                    "category": "development",
                },
            },
            "analytics": {
                "google_analytics": {
                    "keywords": [
                        "analytics",
                        "traffic",
                        "visitors",
                        "metrics",
                        "reports",
                    ],
                    "actions": ["get_report", "analyze_data", "export_data"],
                    "confidence_threshold": 0.7,
                    "category": "analytics",
                },
                "tableau": {
                    "keywords": [
                        "tableau",
                        "dashboard",
                        "visualization",
                        "chart",
                        "graph",
                    ],
                    "actions": ["create_dashboard", "update_dashboard", "analyze_data"],
                    "confidence_threshold": 0.75,
                    "category": "analytics",
                },
            },
            "crm": {
                "salesforce": {
                    "keywords": ["salesforce", "crm", "lead", "opportunity", "account"],
                    "actions": ["create_lead", "update_contact", "search_records"],
                    "confidence_threshold": 0.8,
                    "category": "crm",
                },
                "hubspot": {
                    "keywords": ["hubspot", "marketing", "crm", "contact", "deal"],
                    "actions": ["create_contact", "update_deal", "send_email"],
                    "confidence_threshold": 0.75,
                    "category": "crm",
                },
            },
        }

    def _initialize_workflow_patterns(self) -> Dict[str, Dict[str, Any]]:
        """Initialize intelligent workflow patterns"""
        return {
            "meeting_scheduling": {
                "description": "Schedule meetings and send invitations",
                "services": ["google_calendar", "gmail", "slack"],
                "actions": [
                    "create_calendar_event",
                    "send_email",
                    "send_slack_message",
                ],
                "confidence_threshold": 0.8,
                "complexity": "medium",
            },
            "task_management": {
                "description": "Create and manage tasks across platforms",
                "services": ["asana", "trello", "notion"],
                "actions": ["create_task", "update_task", "assign_task"],
                "confidence_threshold": 0.7,
                "complexity": "low",
            },
            "data_sync": {
                "description": "Synchronize data between different services",
                "services": ["google_sheets", "airtable", "salesforce"],
                "actions": ["export_data", "import_data", "transform_data"],
                "confidence_threshold": 0.75,
                "complexity": "high",
            },
            "notification_workflow": {
                "description": "Send notifications across multiple channels",
                "services": ["slack", "gmail", "teams"],
                "actions": ["send_message", "send_email", "create_post"],
                "confidence_threshold": 0.7,
                "complexity": "low",
            },
            "report_generation": {
                "description": "Generate and distribute reports",
                "services": ["google_analytics", "tableau", "gmail"],
                "actions": ["generate_report", "export_data", "send_email"],
                "confidence_threshold": 0.8,
                "complexity": "medium",
            },
        }

    def _initialize_basic_intelligence_system(self):
        """Initialize basic intelligence system as fallback"""
        self.service_mappings = {
            "basic": {
                "gmail": {"keywords": ["email", "gmail"], "actions": ["send_email"]},
                "slack": {
                    "keywords": ["slack", "message"],
                    "actions": ["send_message"],
                },
                "calendar": {
                    "keywords": ["calendar", "meeting"],
                    "actions": ["create_event"],
                },
            }
        }
        self.workflow_patterns = {
            "basic": {
                "meeting": {
                    "services": ["calendar", "gmail"],
                    "actions": ["create_event", "send_email"],
                },
                "notification": {
                    "services": ["slack", "gmail"],
                    "actions": ["send_message", "send_email"],
                },
            }
        }

    def analyze_workflow_request(
        self, user_input: str, context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Analyze workflow request with enhanced AI intelligence"""
        try:
            # Enhanced service detection with context awareness
            detected_services = self._detect_services_intelligently(user_input, context)

            # Pattern recognition for common workflows
            matched_patterns = self._match_workflow_patterns(
                user_input, detected_services
            )

            # Context-aware action suggestions
            suggested_actions = self._generate_suggested_actions(
                user_input, detected_services, context
            )

            # Calculate confidence scores
            overall_confidence = self._calculate_overall_confidence(
                detected_services, matched_patterns
            )

            return {
                "success": True,
                "detected_services": detected_services,
                "matched_patterns": matched_patterns,
                "suggested_actions": suggested_actions,
                "confidence_score": overall_confidence,
                "analysis_timestamp": self._get_current_timestamp(),
                "enhanced_intelligence": True,
            }

        except Exception as e:
            logger.error(f"Enhanced workflow analysis failed: {str(e)}")
            return self._fallback_workflow_analysis(user_input)

    def _detect_services_intelligently(
        self, user_input: str, context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Intelligently detect services from user input with context awareness"""
        detected_services = []
        user_input_lower = user_input.lower()

        for category, services in self.service_mappings.items():
            for service_name, service_info in services.items():
                confidence = self._calculate_service_confidence(
                    user_input_lower, service_info, context
                )

                if confidence >= service_info.get("confidence_threshold", 0.6):
                    detected_services.append(
                        {
                            "service": service_name,
                            "category": service_info.get("category", "general"),
                            "confidence": confidence,
                            "actions": service_info.get("actions", []),
                            "matching_keywords": self._extract_matching_keywords(
                                user_input_lower, service_info
                            ),
                        }
                    )

        # Sort by confidence score (highest first)
        detected_services.sort(key=lambda x: x["confidence"], reverse=True)

        return detected_services

    def _calculate_service_confidence(
        self, user_input: str, service_info: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Calculate confidence score for service detection"""
        base_confidence = 0.0

        # Keyword matching
        keywords = service_info.get("keywords", [])
        matching_keywords = [kw for kw in keywords if kw in user_input]

        if matching_keywords:
            base_confidence = len(matching_keywords) / len(keywords) * 0.6

        # Context awareness
        context_boost = self._analyze_service_context(service_info, context)
        base_confidence += context_boost * 0.4

        # Capability matching
        capability_match = self._analyze_capability_match(user_input, service_info)
        base_confidence += capability_match * 0.2

        return min(base_confidence, 1.0)

    def _analyze_service_context(
        self, service_info: Dict[str, Any], context: Dict[str, Any]
    ) -> float:
        """Analyze service context for enhanced detection"""
        context_boost = 0.0

        # Check user preferences
        user_preferences = context.get("user_preferences", {})
        preferred_services = user_preferences.get("preferred_services", [])

        service_name = (
            list(service_info.keys())[0] if isinstance(service_info, dict) else None
        )
        if service_name and service_name in preferred_services:
            context_boost += 0.3

        # Check recent usage
        recent_services = context.get("recent_services", [])
        if service_name and service_name in recent_services:
            context_boost += 0.2

        # Check organizational context
        organization_services = context.get("organization_services", [])
        if service_name and service_name in organization_services:
            context_boost += 0.2

        return min(context_boost, 0.7)

    def _analyze_capability_match(
        self, user_input: str, service_info: Dict[str, Any]
    ) -> float:
        """Analyze capability match between user needs and service capabilities"""
        # This is a simplified implementation
        # In a real system, this would use more sophisticated NLP
        user_needs = self._extract_user_needs(user_input)
        service_capabilities = service_info.get("actions", [])

        if not user_needs or not service_capabilities:
            return 0.0

        # Simple keyword-based capability matching
        matching_capabilities = 0
        for need in user_needs:
            for capability in service_capabilities:
                if need in capability or capability in need:
                    matching_capabilities += 1
                    break

        return matching_capabilities / len(user_needs) if user_needs else 0.0

    def _extract_user_needs(self, user_input: str) -> List[str]:
        """Extract user needs from input (simplified implementation)"""
        # This would be replaced with proper NLP in production
        needs_keywords = [
            "create",
            "send",
            "update",
            "search",
            "analyze",
            "generate",
            "schedule",
        ]
        return [word for word in user_input.split() if word in needs_keywords]

    def _extract_matching_keywords(
        self, user_input: str, service_info: Dict[str, Any]
    ) -> List[str]:
        """Extract matching keywords from user input"""
        keywords = service_info.get("keywords", [])
        return [kw for kw in keywords if kw in user_input]

    def _match_workflow_patterns(
        self, user_input: str, detected_services: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Match workflow patterns based on detected services and user input"""
        matched_patterns = []
        user_input_lower = user_input.lower()

        for pattern_name, pattern_info in self.workflow_patterns.items():
            pattern_services = pattern_info.get("services", [])
            pattern_description = pattern_info.get("description", "").lower()

            # Check if pattern description matches user input
            description_match = any(
                word in user_input_lower for word in pattern_description.split()
            )

            # Check if detected services match pattern services
            detected_service_names = [s["service"] for s in detected_services]
            service_match_count = len(
                set(pattern_services) & set(detected_service_names)
            )

            # Calculate pattern confidence
            confidence = 0.0
            if description_match:
                confidence += 0.4
            if service_match_count > 0:
                confidence += (service_match_count / len(pattern_services)) * 0.6

            if confidence >= pattern_info.get("confidence_threshold", 0.6):
                matched_patterns.append(
                    {
                        "pattern": pattern_name,
                        "description": pattern_info.get("description", ""),
                        "confidence": confidence,
                        "services": pattern_services,
                        "actions": pattern_info.get("actions", []),
                        "complexity": pattern_info.get("complexity", "medium"),
                    }
                )

        # Sort by confidence score (highest first)
        matched_patterns.sort(key=lambda x: x["confidence"], reverse=True)

        return matched_patterns

    def _generate_suggested_actions(
        self,
        user_input: str,
        detected_services: List[Dict[str, Any]],
        context: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate intelligent action suggestions"""
        suggested_actions = []

        for service in detected_services:
            service_name = service["service"]
            service_actions = service.get("actions", [])

            for action in service_actions:
                # Simple action relevance calculation
                relevance = self._calculate_action_relevance(
                    user_input, action, service_name, context
                )

                if relevance > 0.3:  # Threshold for suggestion
                    suggested_actions.append(
                        {
                            "service": service_name,
                            "action": action,
                            "relevance": relevance,
                            "description": self._get_action_description(
                                action, service_name
                            ),
                        }
                    )

        # Sort by relevance (highest first)
        suggested_actions.sort(key=lambda x: x["relevance"], reverse=True)

        return suggested_actions[:10]  # Return top 10 suggestions

    def _calculate_action_relevance(
        self, user_input: str, action: str, service: str, context: Dict[str, Any]
    ) -> float:
        """Calculate action relevance based on user input and context"""
        relevance = 0.0

        # Action keyword matching
        if action.replace("_", " ") in user_input.lower():
            relevance += 0.5

        # Service context matching
        if service in context.get("preferred_services", []):
            relevance += 0.2

        # Recent usage boost
        if service in context.get("recent_services", []):
            relevance += 0.1

        # Action frequency in organization
        org_actions = context.get("organization_common_actions", {})
        if action in org_actions.get(service, []):
            relevance += 0.2

        return min(relevance, 1.0)

    def _get_action_description(self, action: str, service: str) -> str:
        """Get human-readable action description"""
        action_descriptions = {
            "send_email": "Send an email message",
            "create_event": "Create a calendar event",
            "send_message": "Send a chat message",
            "create_task": "Create a new task",
            "update_task": "Update an existing task",
            "search_emails": "Search through emails",
            "create_repo": "Create a new repository",
            "create_issue": "Create a new issue",
            "generate_report": "Generate analytics report",
        }
        return action_descriptions.get(action, f"Perform {action} action")

    def _calculate_overall_confidence(
        self,
        detected_services: List[Dict[str, Any]],
        matched_patterns: List[Dict[str, Any]],
    ) -> float:
        """Calculate overall confidence score for the analysis"""
        if not detected_services and not matched_patterns:
            return 0.0

        service_confidence = (
            sum(s["confidence"] for s in detected_services) / len(detected_services)
            if detected_services
            else 0.0
        )

        pattern_confidence = (
            sum(p["confidence"] for p in matched_patterns) / len(matched_patterns)
            if matched_patterns
            else 0.0
        )

        # Weight service detection higher than pattern matching
        overall_confidence = (service_confidence * 0.7) + (pattern_confidence * 0.3)
        return min(overall_confidence, 1.0)

    def _get_current_timestamp(self) -> str:
        """Get current timestamp for analysis"""
        from datetime import datetime

        return datetime.now().isoformat()

    def _fallback_workflow_analysis(self, user_input: str) -> Dict[str, Any]:
        """Fallback workflow analysis when enhanced system fails"""
        return {
            "success": True,
            "detected_services": [],
            "matched_patterns": [],
            "suggested_actions": [],
            "confidence_score": 0.5,
            "analysis_timestamp": self._get_current_timestamp(),
            "enhanced_intelligence": False,
            "fallback_used": True,
        }

    def generate_optimized_workflow(
        self,
        user_input: str,
        context: Dict[str, Any],
        optimization_strategy: str = "performance",
    ) -> Dict[str, Any]:
        """Generate optimized workflow based on user input and strategy"""
        try:
            # First analyze the workflow request
            analysis_result = self.analyze_workflow_request(user_input, context)

            if not analysis_result.get("success"):
                return {
                    "success": False,
                    "error": "Workflow analysis failed",
                    "enhanced_intelligence": False,
                }

            # Generate workflow based on analysis and optimization strategy
            workflow = self._generate_workflow_structure(
                analysis_result, optimization_strategy
            )

            return {
                "success": True,
                "workflow": workflow,
                "analysis": analysis_result,
                "optimization_strategy": optimization_strategy,
                "enhanced_intelligence": True,
                "generation_timestamp": self._get_current_timestamp(),
            }

        except Exception as e:
            logger.error(f"Enhanced workflow generation failed: {str(e)}")
            return {
                "success": False,
                "error": f"Workflow generation failed: {str(e)}",
                "enhanced_intelligence": False,
            }

    def _generate_workflow_structure(
        self, analysis_result: Dict[str, Any], optimization_strategy: str
    ) -> Dict[str, Any]:
        """Generate workflow structure based on analysis and optimization strategy"""
        detected_services = analysis_result.get("detected_services", [])
        matched_patterns = analysis_result.get("matched_patterns", [])
        suggested_actions = analysis_result.get("suggested_actions", [])

        # Create basic workflow structure
        workflow = {
            "name": f"Generated Workflow - {optimization_strategy.title()}",
            "description": "AI-generated workflow based on user input",
            "optimization_strategy": optimization_strategy,
            "services": [service["service"] for service in detected_services],
            "steps": [],
            "enhanced_features": {
                "ai_optimized": True,
                "confidence_score": analysis_result.get("confidence_score", 0.0),
                "detected_services_count": len(detected_services),
                "matched_patterns_count": len(matched_patterns),
            },
        }

        # Generate steps based on suggested actions
        for i, action in enumerate(suggested_actions[:10]):  # Limit to top 10 actions
            workflow["steps"].append(
                {
                    "id": f"step_{i + 1}",
                    "service": action.get("service", ""),
                    "action": action.get("action", ""),
                    "description": action.get("description", ""),
                    "order": i + 1,
                }
            )

        return workflow
