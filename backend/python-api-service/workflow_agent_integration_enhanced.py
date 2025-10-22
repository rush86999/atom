"""
LanceDB-Enhanced Workflow Agent Integration

This module enhances the workflow agent with LanceDB-powered semantic conversation
context retrieval for improved AI workflow generation.
"""

import logging
import uuid
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Tuple
import json

logger = logging.getLogger(__name__)

# Try to import LanceDB for semantic conversation retrieval
try:
    from lancedb_handler import (
        store_conversation_context,
        search_conversation_context,
        get_conversation_history as get_lancedb_conversation_history,
        get_lancedb_connection,
    )

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB integration not available - using SQL fallback")

# Import context management service
from context_management_service import context_management_service


class LanceDBEnhancedWorkflowAgent:
    """
    Enhanced workflow agent that uses LanceDB for semantic conversation context retrieval.
    """

    def __init__(self, base_workflow_agent):
        self.base_agent = base_workflow_agent
        self.logger = logging.getLogger(__name__)

    def process_natural_language_workflow_request(
        self, user_input: str, user_id: str = "default", session_id: str = None
    ) -> Dict[str, Any]:
        """
        Process natural language workflow requests with LanceDB-enhanced context.
        """
        try:
            self.logger.info(
                f"Processing workflow request with LanceDB context: {user_input}"
            )

            # Get user preferences
            user_preferences = context_management_service.get_user_preferences_sync(
                user_id
            )

            # Get LanceDB-enhanced conversation history
            conversation_history = self._get_enhanced_conversation_history(
                user_id, user_input, session_id
            )

            # Add user message to conversation history
            context_management_service.add_conversation_message_sync(
                user_id=user_id,
                session_id=session_id or "default",
                role="user",
                content=user_input,
                message_type="workflow_request",
                metadata={"user_id": user_id, "session_id": session_id},
            )

            # Analyze with enhanced context
            analysis_result = self._analyze_with_semantic_context(
                user_input, user_preferences, conversation_history
            )

            # Generate workflow based on enhanced analysis
            workflow_result = self.base_agent._generate_workflow_from_analysis(
                analysis_result, user_id, session_id
            )

            # Add assistant response to conversation history if successful
            if workflow_result.get("success"):
                context_management_service.add_conversation_message_sync(
                    user_id=user_id,
                    session_id=session_id or "default",
                    role="assistant",
                    content=f"Created workflow: {workflow_result.get('workflow_name', 'Unknown')}",
                    message_type="workflow_response",
                    metadata={
                        "workflow_id": workflow_result.get("workflow_id"),
                        "workflow_name": workflow_result.get("workflow_name"),
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                )

            return workflow_result

        except Exception as e:
            self.logger.error(
                f"Error processing workflow request with LanceDB: {str(e)}"
            )
            # Fall back to base agent
            return self.base_agent.process_natural_language_workflow_request(
                user_input, user_id, session_id
            )

    def _get_enhanced_conversation_history(
        self, user_id: str, current_message: str, session_id: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history enhanced with LanceDB semantic search.
        """
        try:
            # Get chronological history
            chronological_history = (
                context_management_service.get_conversation_history_sync(
                    user_id, session_id, limit=10
                )
            )

            # Get semantically similar conversations from LanceDB
            semantic_history = []
            if LANCEDB_AVAILABLE:
                semantic_history = (
                    context_management_service.search_similar_conversations_sync(
                        user_id, current_message, session_id, limit=5
                    )
                )

            # Combine and deduplicate results
            combined_history = []
            seen_ids = set()

            # Add semantic matches first (most relevant)
            for conv in semantic_history:
                conv_id = f"{conv.get('timestamp')}-{conv.get('content')[:50]}"
                if conv_id not in seen_ids:
                    combined_history.append(conv)
                    seen_ids.add(conv_id)

            # Add chronological history (recent conversations)
            for conv in chronological_history:
                conv_id = f"{conv.get('timestamp')}-{conv.get('content')[:50]}"
                if conv_id not in seen_ids:
                    combined_history.append(conv)
                    seen_ids.add(conv_id)

            # Sort by timestamp (most recent first)
            combined_history.sort(
                key=lambda x: x.get("timestamp", datetime.min), reverse=True
            )

            return combined_history[:15]  # Limit to 15 total messages

        except Exception as e:
            self.logger.warning(f"Failed to get enhanced conversation history: {e}")
            # Fallback to chronological history only
            return context_management_service.get_conversation_history_sync(
                user_id, session_id, limit=10
            )

    def _analyze_with_semantic_context(
        self,
        user_input: str,
        user_preferences: Dict[str, Any],
        conversation_history: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Analyze user input with semantic context from LanceDB.
        """
        # First, use the base analysis
        base_result = self.base_agent._pattern_match_workflow_intent(user_input)

        if not base_result.get("success"):
            return base_result

        # Enhance analysis with user preferences
        preferred_services = user_preferences.get("preferred_services", [])
        automation_level = user_preferences.get("automation_level", "moderate")

        # Adjust service selection based on preferences
        if base_result.get("services"):
            available_services = base_result["services"]
            # Prioritize preferred services
            preferred_available = [
                s for s in available_services if s in preferred_services
            ]
            if preferred_available:
                base_result["services"] = preferred_available
                base_result["preference_boost"] = True

        # Adjust workflow complexity based on automation level
        if automation_level == "minimal":
            base_result["complexity"] = "simple"
            base_result["requires_confirmation"] = True
        elif automation_level == "full":
            base_result["complexity"] = "advanced"
            base_result["requires_confirmation"] = False

        # Analyze conversation history for context
        recent_context = self._extract_context_from_history(conversation_history)
        if recent_context:
            base_result["context_hints"] = recent_context

        # Enhance with semantic understanding from LanceDB
        if len(conversation_history) > 0:
            # Check if we have semantically relevant conversations
            semantic_relevance = self._assess_semantic_relevance(
                conversation_history, user_input
            )
            if semantic_relevance:
                base_result["semantic_relevance"] = semantic_relevance
                # Boost confidence if we have strong semantic matches
                if semantic_relevance.get("strong_matches", 0) > 0:
                    base_result["confidence"] = min(
                        base_result.get("confidence", 0.7) + 0.1, 0.95
                    )

        self.logger.debug(f"LanceDB-enhanced analysis result: {base_result}")
        return base_result

    def _assess_semantic_relevance(
        self, conversation_history: List[Dict[str, Any]], current_input: str
    ) -> Dict[str, Any]:
        """
        Assess semantic relevance of conversation history to current input.
        """
        relevance = {
            "strong_matches": 0,
            "weak_matches": 0,
            "topics_alignment": [],
            "services_alignment": [],
        }

        # Check for conversations with high similarity scores
        for conv in conversation_history:
            similarity = conv.get("similarity_score", 0)
            if similarity > 0.8:
                relevance["strong_matches"] += 1
            elif similarity > 0.6:
                relevance["weak_matches"] += 1

        # Extract topics from current input
        current_topics = set()
        current_input_lower = current_input.lower()

        topic_keywords = {
            "email_management": ["email", "inbox", "message", "gmail"],
            "meeting_management": [
                "meeting",
                "calendar",
                "schedule",
                "appointment",
            ],
            "task_management": ["task", "todo", "reminder", "deadline"],
            "file_management": ["file", "document", "folder", "organize"],
        }

        for topic, keywords in topic_keywords.items():
            if any(keyword in current_input_lower for keyword in keywords):
                current_topics.add(topic)

        # Check topic alignment with conversation history
        for conv in conversation_history:
            conv_content = conv.get("content", "").lower()
            for topic in current_topics:
                topic_keywords = topic_keywords.get(topic, [])
                if any(keyword in conv_content for keyword in topic_keywords):
                    if topic not in relevance["topics_alignment"]:
                        relevance["topics_alignment"].append(topic)

        return relevance

    def _extract_context_from_history(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Extract relevant context from conversation history.
        """
        context = {
            "recent_topics": [],
            "frequent_services": [],
            "workflow_patterns": [],
        }

        if not conversation_history:
            return context

        # Analyze last 5 messages for context
        recent_messages = conversation_history[-5:]

        # Extract topics and services mentioned
        services_mentioned = set()
        topics = set()

        for message in recent_messages:
            content = message["content"].lower()

            # Check for service mentions
            service_keywords = {
                "gmail": ["email", "inbox", "message"],
                "google_calendar": ["meeting", "calendar", "schedule", "appointment"],
                "notion": ["note", "document", "page", "database"],
                "asana": ["task", "project", "todo"],
                "slack": ["message", "channel", "notification"],
                "trello": ["board", "card", "list"],
            }

            for service, keywords in service_keywords.items():
                if any(keyword in content for keyword in keywords):
                    services_mentioned.add(service)

            # Extract potential topics
            if "email" in content:
                topics.add("email_management")
            if "meeting" in content:
                topics.add("meeting_management")
            if "task" in content:
                topics.add("task_management")
            if "file" in content:
                topics.add("file_management")

        context["recent_topics"] = list(topics)
        context["frequent_services"] = list(services_mentioned)

        return context


# Global instance
lancedb_enhanced_workflow_agent = None


def get_lancedb_enhanced_workflow_agent(base_workflow_agent):
    """
    Get or create the LanceDB-enhanced workflow agent instance.
    """
    global lancedb_enhanced_workflow_agent
    if lancedb_enhanced_workflow_agent is None:
        lancedb_enhanced_workflow_agent = LanceDBEnhancedWorkflowAgent(
            base_workflow_agent
        )
    return lancedb_enhanced_workflow_agent
