"""
Chat Orchestrator - Central coordinator for all ATOM features through chat interface

This module provides a unified chat interface that connects all ATOM capabilities:
- 33+ platform integrations
- AI-powered NLP, data intelligence, and automation
- Specialized UIs (Search, Communication, Tasks, Workflows, Scheduling)
- Multi-agent coordination
- Cross-platform workflow execution
"""

import asyncio
import logging
import uuid
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from sqlalchemy.orm import Session

from api.agent_routes import execute_agent_task
from core import unified_search_endpoints, unified_task_endpoints
from core.automation_settings import get_automation_settings
from core.chat_session_manager import get_chat_session_manager
from core.database import get_db_session
from core.unified_task_endpoints import CreateTaskRequest, Task
from core.websockets import get_connection_manager


class SimpleUser:
    """Helper user class for internal calls"""
    def __init__(self, user_id: str):
        self.id = user_id
        self.email = "internal@atom.ai"
        self.username = "atom_internal"

# ... (other imports)
AGENTS = {
    "competitive_intel": {
        "name": "Competitive Intelligence Agent",
        "description": "Tracks competitor pricing and product changes",
        "category": "Market Intelligence"
    },
    "inventory_reconcile": {
        "name": "Inventory Reconciliation Agent",
        "description": "Reconciles inventory counts across systems",
        "category": "Operations"
    },
    "payroll_guardian": {
        "name": "Payroll Guardian Agent",
        "description": "Verifies payroll accuracy and compliance",
        "category": "Finance"
    }
}

# ... (other imports)

logger = logging.getLogger(__name__)

REGULATORY_DISCLAIMER = "\n\n---\n*Disclaimer: ATOM's financial features are powered by AI and intended for strategic guidance. This system is not a licensed CPA or tax advisor. All automated records should be reviewed by a qualified professional before filing.*"


class FeatureType(Enum):
    """Types of ATOM features that can be accessed through chat"""
    SEARCH = "search"
    COMMUNICATION = "communication"
    TASKS = "tasks"
    WORKFLOWS = "workflows"
    SCHEDULING = "scheduling"
    INTEGRATIONS = "integrations"
    AI_ANALYTICS = "ai_analytics"
    AUTOMATION = "automation"
    DOCUMENTS = "documents"
    FINANCE = "finance"
    CRM = "crm"
    SOCIAL_MEDIA = "social_media"
    HR = "hr"
    ECOMMERCE = "ecommerce"
    BUSINESS_HEALTH = "business_health"
    AGENT = "agent"  # Phase 30: Atom Meta-Agent

class PlatformType(Enum):
    """Supported platform integrations"""
    # Communication
    SLACK = "slack"
    TEAMS = "teams"
    GMAIL = "gmail"
    WHATSAPP = "whatsapp"
    OUTLOOK = "outlook"
    ZOOM = "zoom"

    # Task Management
    ASANA = "asana"
    NOTION = "notion"
    TRELLO = "trello"
    LINEAR = "linear"
    JIRA = "jira"

    # File Storage
    GOOGLE_DRIVE = "google_drive"
    ONEDRIVE = "onedrive"
    DROPBOX = "dropbox"
    BOX = "box"

    # Finance
    PLAID = "plaid"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"
    STRIPE = "stripe"

    # CRM & Business
    SALESFORCE = "salesforce"
    HUBSPOT = "hubspot"

    # Social Media
    TWITTER = "twitter"
    LINKEDIN = "linkedin"
    INSTAGRAM = "instagram"
    TIKTOK = "tiktok"

    # Marketing
    MAILCHIMP = "mailchimp"
    CANVA = "canva"
    FIGMA = "figma"

    # HR
    GREENHOUSE = "greenhouse"
    BAMBOOHR = "bamboohr"

    # E-commerce
    SHOPIFY = "shopify"

    # Other
    ZAPIER = "zapier"
    ZOHO = "zoho"
    DOCUSIGN = "docusign"


class ChatIntent(Enum):
    """Chat intent classification"""
    SEARCH_REQUEST = "search_request"
    MESSAGE_SEND = "message_send"
    TASK_MANAGEMENT = "task_management"
    WORKFLOW_CREATION = "workflow_creation"
    SCHEDULING = "scheduling"
    DATA_ANALYSIS = "data_analysis"
    AUTOMATION_TRIGGER = "automation_trigger"
    INTEGRATION_SETUP = "integration_setup"
    STATUS_CHECK = "status_check"
    HELP_REQUEST = "help_request"
    MULTI_STEP_PROCESS = "multi_step_process"
    BUSINESS_HEALTH = "business_health"
    CRM = "crm"
    AGENT_REQUEST = "agent_request"  # Phase 30: Request that needs Atom Meta-Agent
    AI_ANALYTICS = "ai_analytics"


class ChatOrchestrator:
    """
    Main orchestrator that connects chat interface with all ATOM features
    """

    def __init__(self):
        self.conversation_sessions = {}
        self.feature_handlers = {}
        self.platform_connectors = {}
        self.ai_engines = {}
        
        # Initialize session manager for persistence
        self.session_manager = get_chat_session_manager()

        # Initialize feature handlers
        self._initialize_feature_handlers()
        self._initialize_platform_connectors()
        self._initialize_ai_engines()
        
        # Load persisted sessions
        self._load_persisted_sessions()

    def get_user_sessions(self, user_id: str, limit: int = 20) -> Dict[str, Any]:
        """
        Get all sessions for a user, delegating to the session manager (DB/File).
        """
        # Fetch from manager (which handles DB/File abstraction)
        sessions_list = self.session_manager.list_user_sessions(user_id, limit)
        
        # Convert list to dict format expected by frontend (for consistency with current API)
        sessions_dict = {}
        for s in sessions_list:
            sessions_dict[s["session_id"]] = {
                "id": s["session_id"],
                "user_id": s["user_id"],
                "title": s.get("title"), # Added title field
                "created_at": s.get("created_at"),
                "last_updated": s.get("last_active"), 
                "history": s.get("history", []),
                "metadata": s.get("metadata", {})
            }
            
            # Opportunistically cache in memory if missing
            if s["session_id"] not in self.conversation_sessions:
                self.conversation_sessions[s["session_id"]] = sessions_dict[s["session_id"]]
                
        return sessions_dict

    def _load_persisted_sessions(self):
        """Load sessions from disk into memory (Legacy File Support)"""
        try:
             # NOTE: This only loads from file. DB sessions are loaded lazily via get_user_sessions.
            persisted = self.session_manager._load_sessions_file()
            for s in persisted:
                # Convert flat session structure to orchestrator structure
                self.conversation_sessions[s["session_id"]] = {
                    "id": s["session_id"],
                    "user_id": s["user_id"],
                    "created_at": s.get("created_at"),
                    "last_updated": s.get("last_active"), 
                    "history": s.get("history", [])
                }
            logger.info(f"Loaded {len(persisted)} persisted sessions from file.")
        except Exception as e:
            logger.error(f"Failed to load persisted sessions: {e}")

    def _initialize_feature_handlers(self):
        """Initialize handlers for all ATOM features"""
        self.feature_handlers = {
            FeatureType.SEARCH: self._handle_search_request,
            FeatureType.COMMUNICATION: self._handle_communication_request,
            FeatureType.TASKS: self._handle_task_request,
            FeatureType.WORKFLOWS: self._handle_workflow_request,
            FeatureType.SCHEDULING: self._handle_scheduling_request,
            FeatureType.INTEGRATIONS: self._handle_integration_request,
            FeatureType.AI_ANALYTICS: self._handle_ai_analytics_request,
            FeatureType.AUTOMATION: self._handle_automation_request,
            FeatureType.DOCUMENTS: self._handle_document_request,
            FeatureType.FINANCE: self._handle_finance_request,
            FeatureType.CRM: self._handle_crm_request,
            FeatureType.SOCIAL_MEDIA: self._handle_social_media_request,
            FeatureType.HR: self._handle_hr_request,
            FeatureType.ECOMMERCE: self._handle_ecommerce_request,
            FeatureType.BUSINESS_HEALTH: self._handle_business_health_request,
            FeatureType.AGENT: self._handle_agent_request,  # Phase 30: Atom Meta-Agent
        }

    def _initialize_platform_connectors(self):
        """Initialize platform connectors for all integrations"""
        # This would connect to actual platform APIs
        self.platform_connectors = {
            platform: self._create_platform_connector(platform)
            for platform in PlatformType
        }

    def _initialize_ai_engines(self):
        """Initialize AI engines for NLP, data intelligence, and automation"""
        self.ai_engines = {}
        
        # 1. NLP Engine
        try:
            from ai.nlp_engine import NaturalLanguageEngine
            self.ai_engines["nlp"] = NaturalLanguageEngine()
            logger.info("NLP Engine initialized successfully")
        except Exception as e:
            logger.error(f"NLP Engine failed to initialize: {e}")

        # 2. Data Intelligence
        try:
            from ai.data_intelligence import DataIntelligenceEngine
            self.ai_engines["data_intelligence"] = DataIntelligenceEngine()
            logger.info("Data Intelligence Engine initialized successfully")
        except Exception as e:
            logger.error(f"Data Intelligence Engine failed to initialize: {e}")

        # 3. Automation Engine
        try:
            from ai.automation_engine import AutomationEngine
            self.ai_engines["automation"] = AutomationEngine()
            logger.info("Automation Engine initialized successfully")
        except Exception as e:
            logger.error(f"Automation Engine failed to initialize: {e}")

    def _create_platform_connector(self, platform: PlatformType):
        """Create a mock platform connector (would connect to real APIs in production)"""
        return {
            "connected": True,
            "capabilities": ["search", "create", "update", "delete"],
            "metadata": {"platform": platform.value}
        }

    async def _emit_agent_step(self, step: int, thought: str, action: str, observation: str):
        """Emit an agent step update to the frontend via WebSockets"""
        try:
            manager = get_connection_manager()
            # Broadcast to default workspace channel for now
            # In production, this should be f"workspace:{self.current_user.workspace_id}"
            await manager.broadcast_event("workspace:default", "agent_step_update", {
                "step": {
                    "step": step,
                    "thought": thought,
                    "action": action,
                    "action_input": "",
                    "observation": observation,
                    "timestamp": datetime.now().isoformat()
                },
                "agent_id": "system_orchestrator"
            })
        except Exception as e:
            logger.warning(f"Failed to emit agent step: {e}")

    async def process_chat_message(
        self,
        user_id: str,
        message: str,
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Process a chat message and coordinate across all ATOM features

        Args:
            user_id: User identifier
            message: Chat message from user
            session_id: Conversation session ID
            context: Additional context data

        Returns:
            Response with coordinated actions across features
        """
        try:
            # Create or get session
            session_id = session_id or str(uuid.uuid4())
            session = self._get_or_create_session(user_id, session_id)

            # Handle attachments in context
            if context and context.get("attachments"):
                from api.document_routes import _document_store 
                
                attachment_text = "\n\n[USER ATTACHED FILES:]\n"
                has_ctx = False
                
                for att in context["attachments"]:
                    doc_id = att.get("id")
                    if doc_id and doc_id in _document_store:
                        doc = _document_store[doc_id]
                        # Truncate if too long (simple heuristic)
                        content = doc.get('content', '')
                        if len(content) > 10000:
                            content = content[:10000] + "...(truncated)"
                        attachment_text += f"Filename: {doc.get('title')}\nContent:\n{content}\n---\n"
                        has_ctx = True
                
                if has_ctx:
                    logger.info(f"Injecting attachment context for {len(context['attachments'])} files")
                    message = f"{message}\n{attachment_text}"

            # Analyze intent using AI NLP
            intent_analysis = await self._analyze_intent(message, session)

            # Route to appropriate feature handlers
            feature_responses = await self._route_to_features(
                message, intent_analysis, session, context
            )

            # Generate coordinated response
            response = self._generate_coordinated_response(
                message, intent_analysis, feature_responses, session
            )

            # Update session with new context
            self._update_session(session, message, response, intent_analysis)

            return response

        except Exception as e:
            logger.error(f"Error processing chat message: {e}", exc_info=True)
            return self._generate_error_response(str(e), session_id)


    async def _analyze_intent(self, message: str, session: Dict) -> Dict[str, Any]:
        """Analyze user intent using AI NLP engine"""
        
        # Force AI Analytics intent if attachments are present
        if "[USER ATTACHED FILES:]" in message:
             logger.info("Attachment detected, forcing intent to AI_ANALYTICS")
             return {
                "primary_intent": ChatIntent.AI_ANALYTICS,
                "confidence": 1.0,
                "entities": [],
                "platforms": [],
                "command_type": "analyze"
            }

        try:
            if "nlp" in self.ai_engines:
                nlp_result = self.ai_engines["nlp"].parse_command(message)
                return {
                    "primary_intent": self._classify_intent(nlp_result),
                    "confidence": nlp_result.confidence,
                    "entities": nlp_result.entities,
                    "platforms": nlp_result.platforms,
                    "command_type": nlp_result.command_type,
                    "raw_nlp": nlp_result
                }
        except Exception as e:
            logger.warning(f"NLP analysis failed: {e}")

        # Fallback intent classification
        return self._fallback_intent_analysis(message)

    def _classify_intent(self, nlp_result) -> ChatIntent:
        """Classify intent from NLP results"""
        from ai.nlp_engine import CommandType
        command_type = nlp_result.command_type
        
        # Map command types to intents
        intent_mapping = {
            CommandType.SEARCH: ChatIntent.SEARCH_REQUEST,
            CommandType.CREATE: ChatIntent.TASK_MANAGEMENT,
            CommandType.UPDATE: ChatIntent.TASK_MANAGEMENT,
            CommandType.SCHEDULE: ChatIntent.SCHEDULING,
            CommandType.ANALYZE: ChatIntent.DATA_ANALYSIS,
            CommandType.BUSINESS_HEALTH: ChatIntent.BUSINESS_HEALTH,
            CommandType.TRIGGER: ChatIntent.AUTOMATION_TRIGGER,
            CommandType.NOTIFY: ChatIntent.MESSAGE_SEND,
        }

        if command_type in intent_mapping:
            # Special case: "List tasks" often gets misclassified as SEARCH. override it.
            if command_type == CommandType.SEARCH:
                 msg = nlp_result.raw_command.lower()
                 if "list" in msg and ("task" in msg or "todo" in msg):
                     return ChatIntent.TASK_MANAGEMENT
            return intent_mapping[command_type]

        # Handle UNKNOWN with specific text heuristics
        if command_type == CommandType.UNKNOWN:
            msg = nlp_result.raw_command.lower()
            if "list" in msg and ("task" in msg or "todo" in msg):
                 return ChatIntent.TASK_MANAGEMENT
            return ChatIntent.SEARCH_REQUEST # Fallback to search
            
        return ChatIntent.SEARCH_REQUEST

    def _fallback_intent_analysis(self, message: str) -> Dict[str, Any]:
        """Fallback intent analysis when NLP is unavailable"""
        message_lower = message.lower()

        # Simple keyword-based intent detection
        if any(word in message_lower for word in ["find", "search", "look for", "where is"]):
            intent = ChatIntent.SEARCH_REQUEST
        elif any(word in message_lower for word in ["message", "email", "send", "notify"]):
            intent = ChatIntent.MESSAGE_SEND
        elif any(word in message_lower for word in ["task", "todo", "reminder", "due", "list"]):
            intent = ChatIntent.TASK_MANAGEMENT
        elif any(word in message_lower for word in ["workflow", "automate", "automation"]):
            intent = ChatIntent.WORKFLOW_CREATION
        elif any(word in message_lower for word in ["schedule", "meeting", "calendar", "appointment"]):
            intent = ChatIntent.SCHEDULING
        # Business Health Detection
        elif any(word in message_lower for word in ["priority", "priorities", "prioritize", "what should i do", "what to do today"]):
            intent = ChatIntent.BUSINESS_HEALTH
        elif any(word in message_lower for word in ["simulate", "simulation", "what if i", "impact of"]):
            intent = ChatIntent.BUSINESS_HEALTH
        # Automation / Agent Trigger
        elif any(word in message_lower for word in ["run", "execute", "check", "analyze", "inventory", "competitor"]):
             intent = ChatIntent.AUTOMATION_TRIGGER
        # CRM & Sales Intelligence intents
        elif any(word in message_lower for word in ["deal", "lead", "pipeline", "sales", "prospect", "forecast"]):
            intent = ChatIntent.CRM
        else:
            intent = ChatIntent.HELP_REQUEST

        return {
            "primary_intent": intent,
            "confidence": 0.6,
            "entities": [],
            "platforms": [],
            "command_type": "search"
        }

    async def _route_to_features(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        session: Dict,
        context: Optional[Dict]
    ) -> Dict[FeatureType, Any]:
        """Route message to appropriate feature handlers"""
        feature_responses = {}
        primary_intent = intent_analysis["primary_intent"]

        # Map intents to features
        intent_to_features = {
            ChatIntent.SEARCH_REQUEST: [FeatureType.SEARCH, FeatureType.AI_ANALYTICS],
            ChatIntent.MESSAGE_SEND: [FeatureType.COMMUNICATION],
            ChatIntent.TASK_MANAGEMENT: [FeatureType.TASKS, FeatureType.AUTOMATION],
            ChatIntent.WORKFLOW_CREATION: [FeatureType.WORKFLOWS, FeatureType.AUTOMATION],
            ChatIntent.SCHEDULING: [FeatureType.SCHEDULING],
            ChatIntent.DATA_ANALYSIS: [FeatureType.AI_ANALYTICS, FeatureType.SEARCH],
            ChatIntent.AUTOMATION_TRIGGER: [FeatureType.AUTOMATION, FeatureType.WORKFLOWS],
            ChatIntent.INTEGRATION_SETUP: [FeatureType.INTEGRATIONS],
            ChatIntent.STATUS_CHECK: [FeatureType.SEARCH, FeatureType.AI_ANALYTICS],
            ChatIntent.HELP_REQUEST: [FeatureType.SEARCH],
            ChatIntent.BUSINESS_HEALTH: [FeatureType.BUSINESS_HEALTH],
            ChatIntent.CRM: [FeatureType.CRM], # Added CRM intent mapping
            ChatIntent.AGENT_REQUEST: [FeatureType.AGENT],  # Phase 30: Route to Atom
            ChatIntent.MULTI_STEP_PROCESS: list(FeatureType),  # All features for complex requests
            ChatIntent.AI_ANALYTICS: [FeatureType.AI_ANALYTICS],
        }

        target_features = intent_to_features.get(primary_intent, [FeatureType.SEARCH])

        # Execute feature handlers
        for feature_type in target_features:
            if feature_type in self.feature_handlers:
                try:
                    response = await self.feature_handlers[feature_type](
                        message, intent_analysis, session, context
                    )
                    feature_responses[feature_type] = response
                except Exception as e:
                    logger.error(f"Feature handler {feature_type} failed: {e}")
                    feature_responses[feature_type] = {"error": str(e)}

        return feature_responses

    def _generate_coordinated_response(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        feature_responses: Dict[FeatureType, Any],
        session: Dict
    ) -> Dict[str, Any]:
        """Generate coordinated response from all feature responses"""
        # Combine results from all features
        combined_data = {}
        suggested_actions = []
        ui_updates = []

        for feature_type, response in feature_responses.items():
            if response and "data" in response:
                combined_data[feature_type.value] = response["data"]

            if response and "suggested_actions" in response:
                suggested_actions.extend(response["suggested_actions"])

            if response and "ui_updates" in response:
                ui_updates.extend(response["ui_updates"])

        # Generate main response message
        main_message = self._generate_main_message(message, intent_analysis, feature_responses)

        return {
            "success": True,
            "message": main_message,
            "session_id": session["id"],
            "intent": intent_analysis["primary_intent"].value,
            "confidence": intent_analysis["confidence"],
            "data": combined_data,
            "suggested_actions": suggested_actions[:5],  # Limit to top 5
            "ui_updates": ui_updates,
            "requires_confirmation": any(
                resp.get("requires_confirmation", False)
                for resp in feature_responses.values()
            ),
            "next_steps": self._generate_next_steps(intent_analysis, feature_responses),
            "timestamp": datetime.now().isoformat()
        }

    def _generate_main_message(
        self,
        message: str,
        intent_analysis: Dict[str, Any],
        feature_responses: Dict[FeatureType, Any]
    ) -> str:
        """Generate main response message based on feature responses"""
        intent = intent_analysis["primary_intent"]
        
        # DEBUG LOGGING for User Issue
        logger.info(f"DEBUG_CHAT: Intent={intent}, Responses={list(feature_responses.keys())}")
        if FeatureType.SCHEDULING in feature_responses:
            logger.info(f"DEBUG_CHAT: SchedData={feature_responses[FeatureType.SCHEDULING]}")

        if intent == ChatIntent.SEARCH_REQUEST:
            search_data = feature_responses.get(FeatureType.SEARCH, {})
            if search_data.get("data"):
                count = len(search_data["data"].get("results", []))
                return f"I found {count} results for your search."
            return "I've searched across your connected platforms."

        elif intent == ChatIntent.MESSAGE_SEND:
            comm_data = feature_responses.get(FeatureType.COMMUNICATION, {})
            if comm_data.get("success"):
                return "I've sent that message for you."
            return "I'll help you send that message."

        elif intent == ChatIntent.HELP_REQUEST:
             return "Hello! I'm Atom. I can help you manage tasks, schedule meetings, search your data, and more. What would you like to do?"

        elif intent == ChatIntent.TASK_MANAGEMENT:
            task_data = feature_responses.get(FeatureType.TASKS, {})
            # Use specific message from task service if available (e.g. "Task created: Buy Milk")
            if task_data.get("data") and task_data["data"].get("message"):
                return task_data["data"]["message"]
            if task_data.get("data"):
                return "I've updated your tasks across all platforms."
            return "I'll manage those tasks for you."

        elif intent == ChatIntent.WORKFLOW_CREATION:
            workflow_data = feature_responses.get(FeatureType.WORKFLOWS, {})
            if workflow_data.get("message"):
                return workflow_data["message"]
            if workflow_data.get("data"):
                return "Workflow created successfully. Ready to execute?"
            return "I'll create that automation workflow for you."

        elif intent == ChatIntent.SCHEDULING:
            schedule_data = feature_responses.get(FeatureType.SCHEDULING, {})
            # Check for direct message (e.g. auth prompt or error)
            if schedule_data.get("message"):
                return schedule_data["message"]
            # Check for data-embedded message (success case)
            if schedule_data.get("data") and schedule_data["data"].get("message"):
                return schedule_data["data"]["message"]
            return "I'll handle the scheduling for you."

        elif intent == ChatIntent.CRM:
            crm_data = feature_responses.get(FeatureType.CRM, {})
            if crm_data.get("success"):
                return crm_data.get("data", {}).get("answer", "I've processed your CRM request.")
            return "I'll help you with your CRM request."

        elif intent == ChatIntent.BUSINESS_HEALTH:
            health_data = feature_responses.get(FeatureType.BUSINESS_HEALTH, {})
            if health_data.get("success"):
                return health_data.get("message", "I've analyzed your business health.")
            return "I'll help you with your business health query."

        elif intent == ChatIntent.AI_ANALYTICS:
             analytics_data = feature_responses.get(FeatureType.AI_ANALYTICS, {})
             if analytics_data.get("data") and analytics_data["data"].get("message"):
                 return analytics_data["data"]["message"]
             return "I've analyzed the data."

        return "I've processed your request across all connected platforms."

    def _generate_next_steps(
        self,
        intent_analysis: Dict[str, Any],
        feature_responses: Dict[FeatureType, Any]
    ) -> List[str]:
        """Generate suggested next steps"""
        intent = intent_analysis["primary_intent"]
        next_steps = []

        if intent == ChatIntent.SEARCH_REQUEST:
            next_steps.extend([
                "Refine your search with more specific terms",
                "Check the search results in the Search UI",
                "Save important results for quick access"
            ])

        elif intent == ChatIntent.WORKFLOW_CREATION:
            next_steps.extend([
                "Review the workflow steps",
                "Test the workflow execution",
                "Schedule the workflow for automatic runs"
            ])

        elif intent == ChatIntent.TASK_MANAGEMENT:
            next_steps.extend([
                "Set up automatic task creation",
                "Create task templates for recurring work",
                "Coordinate tasks with your team"
            ])
        
        elif intent == ChatIntent.CRM:
            next_steps.extend([
                "View sales pipeline",
                "Create a new lead",
                "Update a deal status"
            ])

        # Add general next steps
        next_steps.extend([
            "Ask me to connect more services",
            "Explore automation opportunities",
            "Check your dashboard for insights"
        ])
        return next_steps[:3]  # Limit to 3 next steps

    # Feature handler implementations
    async def _handle_search_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle search requests across all platforms"""
        try:
            logger.info(f"Handling search request: {message}")
            
            from core import unified_search_endpoints
            from core.unified_search_endpoints import SearchRequest

            # Clean up query
            query = message
            for prefix in ["find", "search for", "show me", "look for", "get"]:
                 if message.lower().startswith(prefix):
                     query = message[len(prefix):].strip()
                     break
            
            user_id = session.get("user_id", "default_user")

            # Call Unified Search
            search_req = SearchRequest(
                query=query,
                user_id=user_id,
                limit=5,
                search_type="hybrid"
            )
            
            
            await self._emit_agent_step(1, f"Searching knowledge base for '{query}'", "search_documents", "Querying hybrid search index...")
            result = await unified_search_endpoints.hybrid_search(search_req)
            await self._emit_agent_step(2, "Search complete", "process_results", f"Found {len(result.results)} relevant documents")
            
            formatted_results = []
            if result.results:
                for r in result.results[:3]:
                    formatted_results.append(f"- [{r.title}]({r.source_uri}) ({r.doc_type})")
                
                response_text = f"I found {len(result.results)} results for '**{query}**':\n" + "\n".join(formatted_results)
            else:
                response_text = f"I couldn't find any documents matching '{query}'."

            return {
                "success": True,
                "data": {
                    "results": [r.dict() for r in result.results],
                    "query": query,
                    "message": response_text
                },
                "suggested_actions": [
                    "Open Search UI for details",
                    "Refine search terms"
                ]
            }
        except Exception as e:
            logger.error(f"Search handler failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_communication_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Communication logic here"}}

    async def _handle_task_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle task requests (Create, List, Update)"""
        try:
            logger.info(f"Handling task request: {intent_analysis}")
            
            # 1. Determine Action (Create vs List)
            # Simple heuristic: if parameters has 'dates' or if intent is 'create', it's likely a create
            action = "create" 
            if "list" in message.lower() or "show" in message.lower() or "what" in message.lower():
                action = "list"
            
            user_id = session.get("user_id", "default_user")
            simple_user = SimpleUser(user_id)

            if action == "create":
                # Extract details
                title = message
                # Try to clean up title by removing trigger words
                for prefix in ["create task", "add task", "remind me to", "new task"]:
                    if message.lower().startswith(prefix):
                        title = message[len(prefix):].strip()
                        break
                
                await self._emit_agent_step(1, "Analyzed intent: Create Task", "create_task", f"Preparing to create task: {title}")
                
                # Check for entities
                entities = intent_analysis.get("entities", [])
                if entities:
                    # If entities found, might use them as title or description
                    pass
                    
                # Create Task Object
                # Default to today if no date found
                due_date = datetime.now() + timedelta(days=1)
                
                await self._emit_agent_step(2, "Defaulting platform based on availability", "check_availability", "Selected platform: Asana (or fallback to local)")

                new_task_req = CreateTaskRequest(
                    title=title,
                    description=f"Created via Chat",
                    dueDate=due_date,
                    priority="medium",
                    platform="asana" if unified_task_endpoints.ASANA_AVAILABLE else "local"
                )
                
                # Call Unified Endpoint
                result = await unified_task_endpoints.create_task(new_task_req, current_user=simple_user)
                
                await self._emit_agent_step(3, "Task created successfully", "finish", f"Task ID: {result['task'].id}")

                return {
                    "success": True, 
                    "data": {
                        "message": f"✅ Task created: **{result['task'].title}** (Due: {result['task'].dueDate.strftime('%Y-%m-%d')})",
                        "task": result['task']
                    }
                }
            
            elif action == "list":
                 # Call Unified Endpoint
                 result = await unified_task_endpoints.get_tasks(platform="all")
                 tasks = result.get("tasks", [])
                 
                 if not tasks:
                     return {"success": True, "data": {"message": "You have no open tasks."}}
                 
                 # Format list
                 task_list_str = "\n".join([f"- **{t.title}** ({t.status})" for t in tasks[:5]])
                 return {
                     "success": True,
                     "data": {
                         "message": f"Here are your tasks:\n{task_list_str}"
                     }
                 }

            return {"success": False, "data": {"message": "I didn't understand the task command."}}
            
        except Exception as e:
            logger.error(f"Task handler failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_workflow_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle workflow creation and management requests"""
        try:
            logger.info(f"Handling workflow request: {message}")
            from core.workflow_template_system import WorkflowTemplateManager

            # Initialize manager
            manager = WorkflowTemplateManager() 
            
            # Simple keyword extraction
            message_lower = message.lower()
            
            # 1. ACTION: LIST
            if any(w in message_lower for w in ["list", "show", "available", "what workflows"]):
                templates = manager.list_templates(limit=10)
                template_list = "\n".join([f"- **{t.name}** ({t.category.value}): {t.description}" for t in templates])
                
                return {
                    "success": True,
                    "message": f"I can help you create workflows from these templates:\n\n{template_list}\n\nJust say 'Create [Template Name] workflow'.",
                    "data": {"templates": [t.dict() for t in templates]},
                    "suggested_actions": [f"Create {t.name} workflow" for t in templates[:3]]
                }

            # 2. ACTION: CREATE
            # Extract potential query from "Create X workflow"
            query = message
            for prefix in ["create", "generate", "build", "make"]:
                if message_lower.startswith(prefix):
                    query = message[len(prefix):].strip()
                    break
            
            # Remove "workflow" keyword to clean search
            query = query.lower().replace("workflow", "").strip()
            
            if not query:
                 return {
                    "success": False,
                    "message": "What kind of workflow would you like to create? You can say 'Create email automation' or 'List templates'."
                }

            # Search for template
            matches = manager.search_templates(query)
            
            if not matches:
                return {
                    "success": False, 
                    "message": f"I couldn't find a template matching '{query}'. Try asking for 'List templates' to see what's available."
                }
            
            best_match = matches[0]
            
            # Create the workflow instance
            # For now, we use default parameters. In a real chat flow, we'd ask for them.
            params = {}
            for input_param in best_match.inputs:
                if input_param.default_value is not None:
                     params[input_param.name] = input_param.default_value
                else:
                     # Placeholder for required params without defaults
                     params[input_param.name] = "user_input_required"

            workflow_name = f"My {best_match.name}"
            
            result = manager.create_workflow_from_template(
                template_id=best_match.template_id,
                workflow_name=workflow_name,
                template_parameters=params
            )
            
            await self._emit_agent_step(1, f"Found template: {best_match.name}", "template_match", f"Instantiating {workflow_name}...")
            await self._emit_agent_step(2, "Workflow Created", "finish", f"Workflow ID: {result['workflow_id']}")

            return {
                "success": True,
                "message": f"✅ **Workflow Created!**\n\nI've generated **{workflow_name}** from the *{best_match.name}* template.\n\nIt has **{len(result['workflow_definition']['steps'])} steps** and is ready to configure.\n\n[Edit in Builder](/workflows/builder?template_id={best_match.template_id})",
                "data": result,
                "suggested_actions": ["Run workflow", "View details", "Create another"]
            }

        except Exception as e:
            logger.error(f"Workflow handler failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_scheduling_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle calendar and meeting requests"""
        from integrations.google_calendar_service import google_calendar_service

        # Check if authenticated
        if not google_calendar_service.authenticate():
            return {
                "success": True, # set to True so frontend processes the message/actions
                "message": "I need permission to access your Google Calendar to schedule this. Please connect your account by clicking the link below:\n\n[Connect Google Calendar](http://localhost:8000/api/auth/google/initiate)",
                "suggested_actions": ["Connect Google Calendar"],
                "data": {
                    "actions": [{
                        "type": "view_calendar",
                        "label": "Connect Google Calendar",
                        "data": { "url": "http://localhost:8000/api/auth/google/initiate" }
                    }]
                },
            }

        message_lower = message.lower()
        
        # Simple extraction simulation (Real app would use NLP entities or specific extraction model)
        # Ideally, we should use the `entities` from intent_analysis if available
        event_topic = "Meeting"
        if "meeting" in message_lower: event_topic = "Team Sync" # enhancing extraction slightly
        if "call" in message_lower: event_topic = "Client Call"
        if "demo" in message_lower: event_topic = "Product Demo"
        
        # Determine time (Basic heuristic for MVP)
        start_time = datetime.now() + timedelta(days=1)
        start_time = start_time.replace(hour=10, minute=0, second=0, microsecond=0)
        
        if "today" in message_lower:
             start_time = datetime.now().replace(hour=16, minute=30, second=0, microsecond=0)
             if start_time < datetime.now(): # If 4:30 PM passed, schedule for next hour
                 start_time = datetime.now() + timedelta(hours=1)
        
        end_time = start_time + timedelta(hours=1)
        
        # Create Unified Event Object
        event_data = {
            "title": event_topic,
            "description": f"Scheduled via ATOM Chat based on request: '{message}'",
            "start_time": start_time.isoformat(),
            "end_time": end_time.isoformat(),
            "location": "Virtual",
            "attendees": [] 
        }

        # Call Real Service
        created_event = await google_calendar_service.create_event(event_data)
        
        if created_event:
            success_message = f"I've scheduled '{created_event['title']}' for {start_time.strftime('%A at %I:%M %p')}."
            return {
                "success": True, 
                "data": {
                    "message": success_message,
                    "event": created_event
                }
            }
        else:
             return {
                "success": False,
                "message": "I encountered an error trying to schedule that event with Google Calendar."
            }

    async def _handle_integration_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Integration logic here"}}

    async def _handle_ai_analytics_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle AI analysis and Q&A requests"""
        try:
            logger.info("Handling AI analytics request with LLM")
            
            if "nlp" not in self.ai_engines:
                 return {"success": False, "data": {"message": "AI Engine not available."}}
            
            nlp_engine = self.ai_engines["nlp"]
            
            # Prepare prompt
            # We assume message already contains the injected [USER ATTACHED FILES] content
            messages = [
                {"role": "system", "content": "You are ATOM, an advanced AI assistant. Analyze the user's request and the provided context (including any attached files). Provide a helpful, concise, and accurate response."},
                {"role": "user", "content": message}
            ]
            
            await self._emit_agent_step(1, "Analyzing content with LLM", "llm_inference", "Generating response...")
            
            response_text = nlp_engine.query_llm(messages)
            
            if not response_text:
                response_text = "I'm sorry, I was unable to generate a response at this time."
                
            await self._emit_agent_step(2, "Response generated", "complete", "Sending response to user")
            
            return {
                "success": True, 
                "data": {
                    "message": response_text
                }
            }
        except Exception as e:
            logger.error(f"AI Analytics handler failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_automation_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle requests to trigger automation agents"""
        message_lower = message.lower()
        
        # Identify which agent to run based on keywords
        target_agent_id = None
        
        if "competitor" in message_lower or "price" in message_lower:
            target_agent_id = "competitive_intel"
        elif "inventory" in message_lower or "stock" in message_lower:
            target_agent_id = "inventory_reconcile"
        elif "payroll" in message_lower:
            target_agent_id = "payroll_guardian"
            
        if not target_agent_id:
            return {
                "success": False, 
                "message": "I understood you want to run an automation, but I'm not sure which one. Try 'Run inventory check' or 'Check competitor prices'."
            }
            
        if target_agent_id not in AGENTS:
             return {
                "success": False, 
                "message": f"Agent configuration for '{target_agent_id}' not found."
            }

        # Trigger the agent using unified execution
        try:
             # In a real app we might pass specific parameters extracted from NLP
            # Explicitly pass workspace_id (default to "default" if not present)
            # This ensures the agent broadcasts events to the correct channel
            current_workspace_id = session.get("workspace_id") or context.get("workspace_id") or "default"
            run_params = {
                "trigger": "chat_user", 
                "session_id": session.get("id"), 
                "workspace_id": current_workspace_id,
                "request": message
            }
            
            # Use execute_agent_task from api.agent_routes
            # Note: execute_agent_task is async
            await execute_agent_task(target_agent_id, run_params)
            
            agent_name = AGENTS[target_agent_id]["name"]
            return {
                "success": True,
                "data": {
                    "agent_id": target_agent_id,
                    "status": "started"
                },
                "message": f"🚀 I've started the **{agent_name}** for you. You'll receive a notification when it completes.",
                "suggested_actions": ["Check Agent Status", "View Live Logs"]
            }
        except Exception as e:
            logger.error(f"Failed to trigger agent {target_agent_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "message": f"I tried to start the agent but encountered an error: {str(e)}"
            }

    async def _handle_document_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Document logic here"}}

    async def _handle_finance_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle financial and accounting queries"""
        if not get_automation_settings().is_accounting_enabled():
            return {
                "success": False,
                "message": "AI Accounting Automations are currently disabled in settings.",
                "suggested_actions": ["Enable Accounting in Settings"]
            }
        try:
            # Generate a DB session
            with get_db_session() as db:
                try:
                    # In a real app, workspace_id comes from context or session
                    workspace_id = context.get("workspace_id") if context else "default-workspace"
                    assistant = AccountingAssistant(db)
                    result = await assistant.process_query(workspace_id, message)

                    # Check for specific AP/AR follow-up actions
                    if "intent" in result:
                        if result["intent"] == "check_overdue":
                            agent = CollectionAgent(db)
                            reminders = await agent.check_overdue_invoices(workspace_id)
                            result["answer"] = f"I've identified {len(reminders)} overdue invoices and triggered reminders."
                            result["reminders"] = reminders
                        elif result["intent"] == "get_aging":
                            agent = CollectionAgent(db)
                            result["aging_report"] = agent.generate_aging_report(workspace_id)
                            result["answer"] = "Here is your current AR aging report summary."
                        elif result["intent"] == "check_close_readiness":
                            agent = CloseChecklistAgent(db)
                            period = result.get("params", {}).get("period", datetime.utcnow().strftime("%Y-%m"))
                            result["close_check"] = await agent.run_close_check(workspace_id, period)
                            result["answer"] = f"Here is the close readiness report for {period}."
                        elif result["intent"] == "get_tax_estimate":
                            service = TaxService(db)
                            result["tax_estimate"] = service.estimate_tax_liability(workspace_id)
                            result["answer"] = "I've calculated your estimated tax liability based on current sales."
                        elif result["intent"] == "get_cash_forecast":
                            service = FPAService(db)
                            result["forecast"] = service.get_13_week_forecast(workspace_id)
                            result["answer"] = "Here is your 13-week cash flow forecast."
                        elif result["intent"] == "run_scenario":
                            service = FPAService(db)
                            # Assume params contains scenario definitions
                            scenarios = result.get("params", {}).get("scenarios", [])
                            result["scenario_results"] = service.run_scenario(workspace_id, scenarios)
                            result["answer"] = "I've modeled the requested scenario and updated the forecast."
                        elif result["intent"] == "get_intercompany_report":
                            manager = IntercompanyManager(db)
                            result["intercompany_report"] = manager.generate_elimination_report(workspace_id)
                            result["answer"] = "Here is the intercompany activity and elimination report."

                        # Append Regulatory Disclaimer to all financial answers
                        if "answer" in result:
                            result["answer"] += REGULATORY_DISCLAIMER

                    return {
                        "success": True,
                        "data": result,
                        "message": result.get("answer", "I've processed your financial request."),
                        "suggested_actions": ["Run P&L Report", "Check AR Aging", "View Unpaid Bills"]
                    }
                except Exception as e:
                    logger.error(f"Finance handler failed: {e}")
                    return {"success": False, "error": str(e)}
        except Exception as e:
            logger.error(f"Finance request failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_crm_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle sales and CRM queries via SalesAssistant"""
        if not get_automation_settings().is_sales_enabled():
            return {
                "success": False,
                "message": "AI Sales Automations are currently disabled in settings.",
                "suggested_actions": ["Enable Sales in Settings"]
            }
        
        try:
            with get_db_session() as db:
                try:
                    from sales.assistant import SalesAssistant
                    workspace_id = context.get("workspace_id") if context else "default-workspace"
                    assistant = SalesAssistant(db)
                    answer = await assistant.answer_sales_query(workspace_id, message)

                    return {
                        "success": True,
                        "data": {"answer": answer},
                        "message": answer[:100] + "...",
                        "suggested_actions": ["View Pipeline", "Check Top Leads", "List My Tasks"]
                    }
                finally:
                    db.close()
        except Exception as e:
            logger.error(f"CRM handler failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_business_health_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """Handle business health queries (priorities and simulations)"""
        # Lazy import 
        from core.business_health_service import business_health_service
        
        message_lower = message.lower()
        workspace_id = context.get("workspace_id") if context else "default-workspace"
        
        try:
            if any(word in message_lower for word in ["priority", "priorities", "prioritize", "what should i do", "what to do today"]):
                # Daily Briefing / Priorities
                health_data = await business_health_service.get_daily_priorities(workspace_id)
                priorities_raw = health_data.get("priorities", [])
                
                # Format for display
                priorities_text = []
                for i, p in enumerate(priorities_raw, 1):
                    priorities_text.append(f"{i}. {p['title']} ({p.get('priority', 'MEDIUM')} Priority)")
                
                owner_advice = health_data.get("owner_advice", "No specific advice generated.")
                timestamp = health_data.get("timestamp", "")
                
                final_msg = (
                    f"Here are your top priorities for today (Generated at {timestamp}):\n\n"
                    f"{chr(10).join(priorities_text)}\n\n"
                    f"💡 **AI Strategic Advice:**\n{owner_advice}"
                )

                return {
                    "success": True, 
                    "message": final_msg,
                    "data": {"priorities": priorities_raw, "advice": owner_advice},
                    "ui_updates": [{"type": "priority_list", "data": priorities_text}],
                    "suggested_actions": ["View Dashboard", "Run Deep Analysis"]
                }
            
            # Only import if we fall through to simulation
            from core.business_health_service import business_health_service
            
            if any(word in message_lower for word in ["simulate", "simulation", "impact", "what if"]):
                # Run Simulation
                # Simple extraction for demo purposes, in production use AI extraction
                decision_type = "GENERAL"
                if "hire" in message_lower or "hiring" in message_lower:
                    decision_type = "HIRING"
                elif "spend" in message_lower or "spent" in message_lower or "buy" in message_lower:
                    decision_type = "CAPEX"
                
                result = await business_health_service.simulate_decision(workspace_id, decision_type, {"query": message})
                answer = result.get("prediction", "I've analyzed the potential impact of this decision.")
                if "roi" in result:
                    answer += f"\n\n**Predicted ROI:** {result['roi']}"
                if "breakeven" in result:
                    answer += f"\n**Breakeven:** {result['breakeven']}"
                
                return {
                    "success": True,
                    "data": result,
                    "message": answer,
                    "suggested_actions": ["Run another simulation", "View cash flow"]
                }
            else:
                # Get Priorities
                result = await business_health_service.get_daily_priorities(workspace_id)
                priorities = result.get("priorities", [])
                advice = result.get("owner_advice", "")
                
                answer = f"**Daily Strategy Insight:**\n{advice}\n\n"
                if priorities:
                    answer += "**Top Priorities:**\n"
                    for p in priorities:
                        answer += f"- [{p['priority']}] **{p['title']}**: {p['description']}\n"
                else:
                    answer += "Your business vitals look great! No urgent actions identified."
                
                return {
                    "success": True,
                    "data": result,
                    "message": answer,
                    "suggested_actions": ["Review Lead Pipeline", "Check Failed Tasks"]
                }
        except Exception as e:
            logger.error(f"Business Health handler failed: {e}")
            return {"success": False, "error": str(e)}

    async def _handle_social_media_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Social Media logic here"}}

    async def _handle_hr_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "HR logic here"}}

    async def _handle_ecommerce_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        return {"success": True, "data": {"message": "Ecommerce logic here"}}

    def _get_or_create_session(self, user_id: str, session_id: str) -> Dict[str, Any]:
        if session_id not in self.conversation_sessions:
            # Check persistence
            persisted = self.session_manager.get_session(session_id)
            
            if persisted:
                # Load from persistence
                self.conversation_sessions[session_id] = {
                    "id": persisted["session_id"],
                    "user_id": persisted["user_id"],
                    "created_at": persisted.get("created_at"),
                    "last_updated": persisted.get("last_active"),
                    "history": persisted.get("history", [])
                }
            else:
                # Create new
                self.session_manager.create_session(user_id, metadata={"source": "chat_orchestrator"}, session_id=session_id)
                self.conversation_sessions[session_id] = {
                    "id": session_id,
                    "user_id": user_id,
                    "created_at": datetime.now().isoformat(),
                    "last_updated": datetime.now().isoformat(),
                    "history": []
                }
        return self.conversation_sessions[session_id]

    def _update_session(self, session: Dict, message: str, response: Dict, intent: Dict):
        # Update memory
        # Ensure intent is serializable
        serializable_intent = intent.copy()
        if "primary_intent" in serializable_intent and hasattr(serializable_intent["primary_intent"], "value"):
            serializable_intent["primary_intent"] = serializable_intent["primary_intent"].value
            
        session["history"].append({
            "message": message,
            "response": response,
            "intent": serializable_intent,
            "timestamp": datetime.now().isoformat()
        })
        session["last_updated"] = datetime.now().isoformat()
        
        # Update persistence
        if self.session_manager:
            self.session_manager.update_session_activity(
                session_id=session["id"], 
                history=session["history"],
                last_message=response.get("message", "Sent a message")
            )

    def _generate_error_response(self, error: str, session_id: str) -> Dict[str, Any]:
        return {
            "success": False,
            "error": error,
            "session_id": session_id,
            "timestamp": datetime.now().isoformat()
        }

    # ==================== PHASE 30: ATOM META-AGENT HANDLER ====================
    
    async def _handle_agent_request(
        self, message: str, intent_analysis: Dict, session: Dict, context: Optional[Dict]
    ) -> Dict[str, Any]:
        """
        Route request to Atom Meta-Agent for complex/agent-based processing.
        Atom will analyze the request, spawn specialty agents if needed, and coordinate response.
        """
        try:
            from core.atom_meta_agent import AgentTriggerMode, get_atom_agent

            # Get user from session if available
            user_id = session.get("user_id", "default_user")
            
            # Get or create Atom instance
            atom = get_atom_agent()
            
            # Execute through Atom
            result = await atom.execute(
                request=message,
                context={
                    "intent_analysis": intent_analysis,
                    "session_id": session.get("id"),
                    "user_id": user_id,
                    **(context or {})
                },
                trigger_mode=AgentTriggerMode.MANUAL
            )
            
            return {
                "status": "success",
                "agent_response": result.get("final_output"),
                "actions_taken": result.get("actions_executed", []),
                "spawned_agent": result.get("spawned_agent"),
                "feature": "agent"
            }
            
        except Exception as e:
            logger.error(f"Agent request handler failed: {e}")
            return {
                "status": "error",
                "error": str(e),
                "feature": "agent"
            }

    def rename_session(self, session_id: str, new_title: str) -> bool:
        """Rename a chat session"""
        
        # 1. Update Persistence
        success = self.session_manager.rename_session(session_id, new_title)
        
        # 2. Update In-Memory Cache if present
        if session_id in self.conversation_sessions:
            self.conversation_sessions[session_id]["title"] = new_title
            
        return success
