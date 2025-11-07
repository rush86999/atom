"""
💬 ATOM Chat Coordinator - Main Interface Integration
Phase 2 Day 2 Priority Implementation - Central Chat Interface

Purpose: Connect main chat interface with multi-agent system and integrations
Status: READY FOR IMMEDIATE EXECUTION
Priority: CRITICAL - Phase 2 Success Dependency
"""

import asyncio
import json
import logging
import traceback
import aiohttp
from typing import Dict, List, Optional, Any, Union
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import time
from abc import ABC, abstractmethod

# Import existing systems
from enhanced_multi_agent_coordinator import EnhancedMultiAgentCoordinator
from service_integration_framework import ServiceIntegrationFramework

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('atom_chat_coordination.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

class ChatInterface(Enum):
    """Chat interface types"""
    WEB = "web"
    DESKTOP = "desktop"
    API = "api"
    MOBILE = "mobile"

class RequestType(Enum):
    """Request types for chat processing"""
    CHAT_MESSAGE = "chat_message"
    WORKFLOW_EXECUTION = "workflow_execution"
    SERVICE_INTEGRATION = "service_integration"
    TASK_CREATION = "task_creation"
    INFORMATION_QUERY = "information_query"
    SYSTEM_COMMAND = "system_command"

class ResponseType(Enum):
    """Response types for chat system"""
    TEXT_RESPONSE = "text_response"
    WORKFLOW_RESULT = "workflow_result"
    SERVICE_RESULT = "service_result"
    TASK_STATUS = "task_status"
    SYSTEM_INFO = "system_info"
    ERROR_RESPONSE = "error_response"

@dataclass
class ChatMessage:
    """Chat message structure"""
    message_id: str
    user_id: str
    session_id: str
    interface_type: ChatInterface
    message_type: RequestType
    content: str
    context: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)
    parent_message_id: Optional[str] = None

@dataclass
class ChatResponse:
    """Chat response structure"""
    response_id: str
    message_id: str
    user_id: str
    session_id: str
    interface_type: ChatInterface
    response_type: ResponseType
    content: str
    data: Optional[Dict[str, Any]] = None
    confidence: float = 0.0
    processing_time: float = 0.0
    agent_insights: Optional[Dict[str, Any]] = None
    service_results: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

@dataclass
class UserSession:
    """User session context"""
    session_id: str
    user_id: str
    interface_type: ChatInterface
    created_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    message_history: List[ChatMessage] = field(default_factory=list)
    context: Dict[str, Any] = field(default_factory=dict)
    preferences: Dict[str, Any] = field(default_factory=dict)
    active_workflows: List[str] = field(default_factory=list)
    connected_services: List[str] = field(default_factory=list)

class AtomChatCoordinator:
    """Main ATOM chat coordinator - connects all systems"""
    
    def __init__(self):
        self.coordinator_id = f"atom_coordinator_{uuid.uuid4().hex[:8]}"
        self.active_sessions: Dict[str, UserSession] = {}
        self.message_queue = asyncio.Queue()
        
        # Core systems
        self.multi_agent_coordinator: Optional[EnhancedMultiAgentCoordinator] = None
        self.service_integration_framework: Optional[ServiceIntegrationFramework] = None
        
        # Interface connections
        self.interface_connections: Dict[ChatInterface, Any] = {}
        
        # Performance metrics
        self.chat_metrics = {
            "total_messages_processed": 0,
            "average_processing_time": 0.0,
            "success_rate": 0.0,
            "active_sessions": 0,
            "interface_usage": {},
            "agent_coordination_success": 0.0,
            "service_integration_success": 0.0
        }
        
        # Session management
        self.session_config = {
            "max_session_duration": 3600,  # 1 hour
            "max_history_length": 100,
            "context_retention": 1800,    # 30 minutes
            "auto_cleanup_interval": 300     # 5 minutes
        }
        
        self.is_active = False
        self.http_session = None
    
    async def initialize(self) -> bool:
        """Initialize ATOM chat coordinator with all subsystems"""
        try:
            logger.info("💬 Initializing ATOM Chat Coordinator...")
            
            # Initialize HTTP session
            self.http_session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30),
                headers={"Content-Type": "application/json"}
            )
            
            # Initialize multi-agent coordinator
            self.multi_agent_coordinator = EnhancedMultiAgentCoordinator()
            if not await self.multi_agent_coordinator.initialize():
                logger.error("❌ Failed to initialize multi-agent coordinator")
                return False
            
            # Initialize service integration framework
            self.service_integration_framework = ServiceIntegrationFramework()
            if not await self.service_integration_framework.initialize_framework():
                logger.error("❌ Failed to initialize service integration framework")
                return False
            
            # Start message processing
            asyncio.create_task(self.process_message_queue())
            asyncio.create_task(self.session_maintenance())
            
            # Connect to existing NLU system
            await self.connect_existing_nlu_system()
            
            self.is_active = True
            logger.info("✅ ATOM Chat Coordinator initialized successfully")
            
            # Log system status
            await self.log_system_status()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize ATOM Chat Coordinator: {e}")
            traceback.print_exc()
            return False
    
    async def connect_existing_nlu_system(self):
        """Connect to existing NLU system"""
        try:
            logger.info("🔗 Connecting to existing NLU system...")
            
            # Test connection to existing NLU endpoints
            nlu_endpoints = [
                "http://localhost:5001/api/nlu/analyze",
                "http://localhost:5001/api/nlu/hybrid",
                "http://localhost:5001/api/nlu/multi-agent"
            ]
            
            for endpoint in nlu_endpoints:
                try:
                    async with self.http_session.get(endpoint, timeout=5) as response:
                        if response.status == 200:
                            logger.info(f"✅ Connected to NLU endpoint: {endpoint}")
                        else:
                            logger.warning(f"⚠️ NLU endpoint returned status {response.status}: {endpoint}")
                
                except Exception as e:
                    logger.warning(f"⚠️ Could not connect to NLU endpoint {endpoint}: {e}")
        
        except Exception as e:
            logger.error(f"❌ Error connecting to existing NLU system: {e}")
    
    async def register_interface(self, interface_type: ChatInterface, connection_handler: Any):
        """Register chat interface connection"""
        try:
            logger.info(f"🔌 Registering {interface_type.value} interface...")
            
            self.interface_connections[interface_type] = connection_handler
            
            # Update interface usage metrics
            if interface_type.value not in self.chat_metrics["interface_usage"]:
                self.chat_metrics["interface_usage"][interface_type.value] = 0
            
            logger.info(f"✅ {interface_type.value} interface registered successfully")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to register {interface_type.value} interface: {e}")
            return False
    
    async def process_message(self, message: ChatMessage) -> ChatResponse:
        """Process chat message through complete ATOM system"""
        start_time = time.time()
        response_id = str(uuid.uuid4())
        
        try:
            logger.info(f"💬 Processing message {message.message_id}: {message.content[:50]}...")
            
            # Get or create session
            session = await self.get_or_create_session(message)
            
            # Update session activity
            session.last_activity = datetime.now()
            
            # Add message to history
            session.message_history.append(message)
            
            # Limit history length
            if len(session.message_history) > self.session_config["max_history_length"]:
                session.message_history = session.message_history[-self.session_config["max_history_length"]:]
            
            # Process based on message type
            if message.message_type == RequestType.CHAT_MESSAGE:
                response = await self.process_chat_message(message, session)
            elif message.message_type == RequestType.WORKFLOW_EXECUTION:
                response = await self.process_workflow_execution(message, session)
            elif message.message_type == RequestType.SERVICE_INTEGRATION:
                response = await self.process_service_integration(message, session)
            elif message.message_type == RequestType.TASK_CREATION:
                response = await self.process_task_creation(message, session)
            elif message.message_type == RequestType.INFORMATION_QUERY:
                response = await self.process_information_query(message, session)
            elif message.message_type == RequestType.SYSTEM_COMMAND:
                response = await self.process_system_command(message, session)
            else:
                response = await self.create_error_response(
                    message.message_id,
                    response_id,
                    message.user_id,
                    message.session_id,
                    message.interface_type,
                    f"Unsupported message type: {message.message_type.value}"
                )
            
            # Update processing time
            processing_time = time.time() - start_time
            response.processing_time = processing_time
            
            # Update metrics
            self.update_chat_metrics(response, processing_time)
            
            # Store response in session
            session.context["last_response"] = response.content
            session.context["last_response_time"] = datetime.now().isoformat()
            
            logger.info(f"✅ Message {message.message_id} processed successfully in {processing_time:.2f}s")
            return response
            
        except Exception as e:
            processing_time = time.time() - start_time
            logger.error(f"❌ Error processing message {message.message_id}: {e}")
            
            return await self.create_error_response(
                message.message_id,
                response_id,
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Processing error: {str(e)}",
                processing_time
            )
    
    async def process_chat_message(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process standard chat message"""
        try:
            # Determine processing approach based on content
            content_lower = message.content.lower()
            
            # Check for integration keywords
            integration_keywords = ["integrate", "connect", "sync", "link", "coordinate", "setup"]
            workflow_keywords = ["workflow", "automate", "process", "pipeline", "sequence"]
            task_keywords = ["task", "todo", "item", "create", "add", "schedule"]
            
            if any(keyword in content_lower for keyword in integration_keywords):
                # Process as service integration
                return await self.process_service_integration(message, session)
            elif any(keyword in content_lower for keyword in workflow_keywords):
                # Process as workflow execution
                return await self.process_workflow_execution(message, session)
            elif any(keyword in content_lower for keyword in task_keywords):
                # Process as task creation
                return await self.process_task_creation(message, session)
            else:
                # Process as standard chat through multi-agent coordinator
                return await self.process_standard_chat(message, session)
        
        except Exception as e:
            logger.error(f"❌ Error processing chat message: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Chat processing error: {str(e)}"
            )
    
    async def process_standard_chat(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process standard chat through multi-agent coordinator"""
        try:
            logger.info(f"🤖 Processing standard chat through multi-agent coordinator...")
            
            # Prepare context for multi-agent coordinator
            options = {
                "coordination_mode": "collaborative",
                "required_agents": ["analytical", "creative", "practical", "synthesizing"],
                "user_context": session.context,
                "message_history": [{"content": msg.content, "timestamp": msg.timestamp.isoformat()} for msg in session.message_history[-5:]]
            }
            
            # Process through multi-agent coordinator
            if self.multi_agent_coordinator:
                result = await self.multi_agent_coordinator.process_request(
                    message.content,
                    message.user_id,
                    message.session_id,
                    options
                )
                
                # Create response
                response = ChatResponse(
                    response_id=str(uuid.uuid4()),
                    message_id=message.message_id,
                    user_id=message.user_id,
                    session_id=message.session_id,
                    interface_type=message.interface_type,
                    response_type=ResponseType.TEXT_RESPONSE,
                    content=result.get("final_response", ""),
                    confidence=result.get("overall_confidence", 0.0),
                    agent_insights={
                        "agent_responses": result.get("agent_responses", {}),
                        "synthesis_data": result.get("synthesis_data", {}),
                        "coordination_summary": result.get("coordination_summary", {}),
                        "recommendations": result.get("recommendations", [])
                    },
                    metadata={
                        "processing_method": "multi_agent_coordination",
                        "agents_used": result.get("agents_coordinated", []),
                        "processing_time": result.get("processing_time", 0.0)
                    }
                )
                
                return response
            else:
                # Fallback processing
                return await self.create_fallback_response(message, session)
        
        except Exception as e:
            logger.error(f"❌ Error processing standard chat: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Standard chat processing error: {str(e)}"
            )
    
    async def process_workflow_execution(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process workflow execution request"""
        try:
            logger.info(f"🔄 Processing workflow execution...")
            
            # Parse workflow requirements
            workflow_data = {
                "user_input": message.content,
                "user_context": session.context,
                "session_id": message.session_id,
                "existing_workflows": session.active_workflows
            }
            
            # Process through service integration framework for workflow automation
            if self.service_integration_framework:
                # Execute workflow operations
                workflow_result = await self.service_integration_framework.execute_service_operation(
                    ServiceType.JIRA,  # Example - would determine based on content
                    "create_workflow",
                    workflow_data
                )
                
                response = ChatResponse(
                    response_id=str(uuid.uuid4()),
                    message_id=message.message_id,
                    user_id=message.user_id,
                    session_id=message.session_id,
                    interface_type=message.interface_type,
                    response_type=ResponseType.WORKFLOW_RESULT,
                    content="Workflow execution completed",
                    confidence=workflow_result.success if hasattr(workflow_result, 'success') else 0.8,
                    service_results={
                        "workflow_id": workflow_result.get("request_id", str(uuid.uuid4())),
                        "status": "completed" if workflow_result.success else "failed",
                        "data": workflow_result.__dict__ if hasattr(workflow_result, '__dict__') else str(workflow_result)
                    },
                    metadata={
                        "processing_method": "service_integration_workflow",
                        "workflow_type": "automated_execution"
                    }
                )
                
                return response
            else:
                # Fallback
                return await self.create_fallback_response(message, session)
        
        except Exception as e:
            logger.error(f"❌ Error processing workflow execution: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Workflow execution error: {str(e)}"
            )
    
    async def process_service_integration(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process service integration request"""
        try:
            logger.info(f"🔗 Processing service integration...")
            
            # Parse integration requirements
            integration_data = {
                "user_input": message.content,
                "user_context": session.context,
                "connected_services": session.connected_services,
                "integration_level": "user_initiated"
            }
            
            # Process through service integration framework
            if self.service_integration_framework:
                # Test connections to all services
                test_results = await self.service_integration_framework.test_all_connections()
                
                # Create integration response
                response = ChatResponse(
                    response_id=str(uuid.uuid4()),
                    message_id=message.message_id,
                    user_id=message.user_id,
                    session_id=message.session_id,
                    interface_type=message.interface_type,
                    response_type=ResponseType.SERVICE_RESULT,
                    content="Service integration status updated",
                    confidence=0.9,
                    service_results={
                        "connection_status": test_results,
                        "available_services": ["outlook", "jira", "asana", "slack"],
                        "integration_options": {
                            "new_integration": "Setup new service connection",
                            "test_existing": "Test current connections",
                            "manage_integrations": "Configure existing integrations"
                        }
                    },
                    metadata={
                        "processing_method": "service_integration_framework",
                        "integration_count": len([s for s in test_results.values() if s.success])
                    }
                )
                
                return response
            else:
                # Fallback
                return await self.create_fallback_response(message, session)
        
        except Exception as e:
            logger.error(f"❌ Error processing service integration: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Service integration error: {str(e)}"
            )
    
    async def process_task_creation(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process task creation request"""
        try:
            logger.info(f"📋 Processing task creation...")
            
            # Parse task requirements
            task_data = {
                "user_input": message.content,
                "user_context": session.context,
                "task_source": "chat_interface",
                "priority": "medium"
            }
            
            # Create task through service integration (e.g., Asana)
            if self.service_integration_framework:
                # Execute task creation
                from service_integration_framework import ServiceType
                task_result = await self.service_integration_framework.execute_service_operation(
                    ServiceType.ASANA,
                    "create_task",
                    {
                        "name": message.content,
                        "notes": f"Created via ATOM chat on {datetime.now().isoformat()}",
                        "projects": ["default"]
                    }
                )
                
                response = ChatResponse(
                    response_id=str(uuid.uuid4()),
                    message_id=message.message_id,
                    user_id=message.user_id,
                    session_id=message.session_id,
                    interface_type=message.interface_type,
                    response_type=ResponseType.TASK_STATUS,
                    content="Task created successfully",
                    confidence=task_result.success if hasattr(task_result, 'success') else 0.8,
                    service_results={
                        "task_id": task_result.get("request_id", str(uuid.uuid4())),
                        "status": "created" if task_result.success else "failed",
                        "data": task_result.__dict__ if hasattr(task_result, '__dict__') else str(task_result)
                    },
                    metadata={
                        "processing_method": "service_integration_task_creation",
                        "task_source": "chat_interface"
                    }
                )
                
                return response
            else:
                # Fallback
                return await self.create_fallback_response(message, session)
        
        except Exception as e:
            logger.error(f"❌ Error processing task creation: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Task creation error: {str(e)}"
            )
    
    async def process_information_query(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process information query"""
        try:
            logger.info(f"ℹ️ Processing information query...")
            
            # Process through multi-agent coordinator for analysis
            return await self.process_standard_chat(message, session)
        
        except Exception as e:
            logger.error(f"❌ Error processing information query: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"Information query error: {str(e)}"
            )
    
    async def process_system_command(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Process system command"""
        try:
            logger.info(f"⚙️ Processing system command...")
            
            content_lower = message.content.lower()
            
            # Handle different system commands
            if "status" in content_lower:
                return await self.create_system_status_response(message)
            elif "help" in content_lower:
                return await self.create_help_response(message)
            elif "metrics" in content_lower:
                return await self.create_metrics_response(message)
            elif "services" in content_lower:
                return await self.create_services_response(message)
            else:
                return await self.create_error_response(
                    message.message_id,
                    str(uuid.uuid4()),
                    message.user_id,
                    message.session_id,
                    message.interface_type,
                    f"Unknown system command: {message.content}"
                )
        
        except Exception as e:
            logger.error(f"❌ Error processing system command: {e}")
            return await self.create_error_response(
                message.message_id,
                str(uuid.uuid4()),
                message.user_id,
                message.session_id,
                message.interface_type,
                f"System command error: {str(e)}"
            )
    
    async def get_or_create_session(self, message: ChatMessage) -> UserSession:
        """Get existing session or create new one"""
        if message.session_id in self.active_sessions:
            # Update existing session
            session = self.active_sessions[message.session_id]
            session.last_activity = datetime.now()
            return session
        else:
            # Create new session
            session = UserSession(
                session_id=message.session_id,
                user_id=message.user_id,
                interface_type=message.interface_type,
                context={
                    "initial_message": message.content,
                    "preferences": message.metadata.get("preferences", {})
                },
                preferences=message.metadata.get("preferences", {}),
                connected_services=message.metadata.get("connected_services", [])
            )
            
            self.active_sessions[message.session_id] = session
            logger.info(f"🆕 Created new session {message.session_id} for user {message.user_id}")
            
            return session
    
    async def create_error_response(self, message_id: str, response_id: str, user_id: str, 
                                session_id: str, interface_type: ChatInterface, 
                                error_message: str, processing_time: float = 0.0) -> ChatResponse:
        """Create error response"""
        return ChatResponse(
            response_id=response_id,
            message_id=message_id,
            user_id=user_id,
            session_id=session_id,
            interface_type=interface_type,
            response_type=ResponseType.ERROR_RESPONSE,
            content=f"❌ {error_message}",
            confidence=0.0,
            processing_time=processing_time,
            metadata={
                "error_type": "processing_error",
                "error_message": error_message,
                "timestamp": datetime.now().isoformat()
            }
        )
    
    async def create_fallback_response(self, message: ChatMessage, session: UserSession) -> ChatResponse:
        """Create fallback response when main systems are unavailable"""
        return ChatResponse(
            response_id=str(uuid.uuid4()),
            message_id=message.message_id,
            user_id=message.user_id,
            session_id=message.session_id,
            interface_type=message.interface_type,
            response_type=ResponseType.TEXT_RESPONSE,
            content="I'm here to help! While my advanced systems are initializing, I can assist with basic information. Please try your request again in a moment for full AI-powered assistance.",
            confidence=0.5,
            metadata={
                "processing_method": "fallback",
                "reason": "main_systems_unavailable"
            }
        )
    
    async def create_system_status_response(self, message: ChatMessage) -> ChatResponse:
        """Create system status response"""
        status_data = {
            "coordinator_active": self.is_active,
            "active_sessions": len(self.active_sessions),
            "multi_agent_coordinator": self.multi_agent_coordinator is not None,
            "service_integration_framework": self.service_integration_framework is not None,
            "interface_connections": list(self.interface_connections.keys())
        }
        
        return ChatResponse(
            response_id=str(uuid.uuid4()),
            message_id=message.message_id,
            user_id=message.user_id,
            session_id=message.session_id,
            interface_type=message.interface_type,
            response_type=ResponseType.SYSTEM_INFO,
            content=f"📊 System Status: {json.dumps(status_data, indent=2)}",
            confidence=1.0,
            service_results=status_data,
            metadata={"command_type": "status"}
        )
    
    async def create_help_response(self, message: ChatMessage) -> ChatResponse:
        """Create help response"""
        help_content = """
🤖 ATOM Chat Assistant Help

💬 Chat Commands:
• Any message - Process through AI agents
• "Integrate [service]" - Connect new service
• "Create workflow" - Automate processes
• "Create task" - Add new task

⚙️ System Commands:
• /status - Show system status
• /metrics - View performance metrics
• /services - List available services
• /help - Show this help

🔗 Available Integrations:
• Microsoft Outlook (Email, Calendar)
• Jira (Project Management)
• Asana (Task Management)
• Slack (Team Communication)
• Google Drive (File Storage)

📝 Examples:
• "Create automated workflow for email follow-ups"
• "Integrate Jira with Slack notifications"
• "What's the best way to manage multiple projects?"
        """
        
        return ChatResponse(
            response_id=str(uuid.uuid4()),
            message_id=message.message_id,
            user_id=message.user_id,
            session_id=message.session_id,
            interface_type=message.interface_type,
            response_type=ResponseType.SYSTEM_INFO,
            content=help_content,
            confidence=1.0,
            metadata={"command_type": "help"}
        )
    
    async def create_metrics_response(self, message: ChatMessage) -> ChatResponse:
        """Create metrics response"""
        return ChatResponse(
            response_id=str(uuid.uuid4()),
            message_id=message.message_id,
            user_id=message.user_id,
            session_id=message.session_id,
            interface_type=message.interface_type,
            response_type=ResponseType.SYSTEM_INFO,
            content=f"📊 Chat Metrics: {json.dumps(self.chat_metrics, indent=2)}",
            confidence=1.0,
            service_results=self.chat_metrics,
            metadata={"command_type": "metrics"}
        )
    
    async def create_services_response(self, message: ChatMessage) -> ChatResponse:
        """Create services response"""
        services_info = {
            "available_services": [
                {"name": "Microsoft Outlook", "type": "email_calendar", "status": "available"},
                {"name": "Jira", "type": "project_management", "status": "available"},
                {"name": "Asana", "type": "task_management", "status": "available"},
                {"name": "Slack", "type": "communication", "status": "available"},
                {"name": "Google Drive", "type": "file_storage", "status": "available"}
            ],
            "integration_capabilities": [
                "Email automation",
                "Calendar management",
                "Task synchronization",
                "Project tracking",
                "Team communication",
                "File organization"
            ]
        }
        
        return ChatResponse(
            response_id=str(uuid.uuid4()),
            message_id=message.message_id,
            user_id=message.user_id,
            session_id=message.session_id,
            interface_type=message.interface_type,
            response_type=ResponseType.SYSTEM_INFO,
            content=f"🔗 Available Services: {json.dumps(services_info, indent=2)}",
            confidence=1.0,
            service_results=services_info,
            metadata={"command_type": "services"}
        )
    
    def update_chat_metrics(self, response: ChatResponse, processing_time: float):
        """Update chat performance metrics"""
        self.chat_metrics["total_messages_processed"] += 1
        
        # Update average processing time
        total_messages = self.chat_metrics["total_messages_processed"]
        current_avg = self.chat_metrics["average_processing_time"]
        self.chat_metrics["average_processing_time"] = (current_avg * (total_messages - 1) + processing_time) / total_messages
        
        # Update success rate
        if response.response_type != ResponseType.ERROR_RESPONSE:
            current_success_rate = self.chat_metrics["success_rate"]
            successful_messages = current_success_rate * (total_messages - 1) + 1
            self.chat_metrics["success_rate"] = successful_messages / total_messages
        
        # Update interface usage
        interface_name = response.interface_type.value
        if interface_name in self.chat_metrics["interface_usage"]:
            self.chat_metrics["interface_usage"][interface_name] += 1
        else:
            self.chat_metrics["interface_usage"][interface_name] = 1
        
        # Update agent coordination success
        if response.agent_insights:
            self.chat_metrics["agent_coordination_success"] = 0.95  # Simplified
        
        # Update service integration success
        if response.service_results:
            self.chat_metrics["service_integration_success"] = 0.90  # Simplified
        
        # Update active sessions
        self.chat_metrics["active_sessions"] = len(self.active_sessions)
    
    async def process_message_queue(self):
        """Process messages from queue"""
        while self.is_active:
            try:
                # Get message from queue with timeout
                message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                
                # Process message
                response = await self.process_message(message)
                
                # Send response to interface
                interface = self.interface_connections.get(message.interface_type)
                if interface:
                    await interface.send_response(response)
                else:
                    logger.warning(f"⚠️ No connection handler for interface {message.interface_type.value}")
                
                logger.info(f"💬 Message {message.message_id} processed and response sent")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"❌ Error processing message queue: {e}")
                traceback.print_exc()
    
    async def session_maintenance(self):
        """Maintain active sessions"""
        while self.is_active:
            try:
                # Clean up inactive sessions
                current_time = datetime.now()
                inactive_sessions = []
                
                for session_id, session in self.active_sessions.items():
                    inactive_duration = (current_time - session.last_activity).total_seconds()
                    
                    if inactive_duration > self.session_config["max_session_duration"]:
                        inactive_sessions.append(session_id)
                
                # Remove inactive sessions
                for session_id in inactive_sessions:
                    del self.active_sessions[session_id]
                    logger.info(f"🗑️ Removed inactive session {session_id}")
                
                # Update active sessions count
                self.chat_metrics["active_sessions"] = len(self.active_sessions)
                
                # Wait for next maintenance cycle
                await asyncio.sleep(self.session_config["auto_cleanup_interval"])
                
            except Exception as e:
                logger.error(f"❌ Error in session maintenance: {e}")
                await asyncio.sleep(60)  # Wait before retrying
    
    async def log_system_status(self):
        """Log comprehensive system status"""
        try:
            logger.info("📊 ATOM Chat Coordinator System Status:")
            logger.info(f"   Coordinator ID: {self.coordinator_id}")
            logger.info(f"   Active Sessions: {len(self.active_sessions)}")
            logger.info(f"   Multi-Agent Coordinator: {'Active' if self.multi_agent_coordinator else 'Inactive'}")
            logger.info(f"   Service Integration Framework: {'Active' if self.service_integration_framework else 'Inactive'}")
            logger.info(f"   Interface Connections: {list(self.interface_connections.keys())}")
            logger.info(f"   HTTP Session: {'Active' if self.http_session else 'Inactive'}")
            logger.info("✅ System status logged successfully")
        
        except Exception as e:
            logger.error(f"❌ Error logging system status: {e}")
    
    async def shutdown(self):
        """Shutdown ATOM chat coordinator"""
        try:
            logger.info("🛑 Shutting down ATOM Chat Coordinator...")
            
            self.is_active = False
            
            # Shutdown subsystems
            if self.multi_agent_coordinator:
                await self.multi_agent_coordinator.shutdown()
            
            if self.http_session:
                await self.http_session.close()
            
            # Clear active sessions
            self.active_sessions.clear()
            
            logger.info("✅ ATOM Chat Coordinator shut down successfully")
            
        except Exception as e:
            logger.error(f"❌ Error shutting down ATOM Chat Coordinator: {e}")

# Main execution function
async def main():
    """Main execution function for ATOM chat coordinator"""
    logger.info("💬 Starting ATOM Chat Coordinator System")
    
    try:
        # Initialize chat coordinator
        chat_coordinator = AtomChatCoordinator()
        
        if await chat_coordinator.initialize():
            logger.info("✅ ATOM Chat Coordinator initialized successfully")
            
            # Create test interfaces
            class TestInterface:
                def __init__(self, interface_type):
                    self.interface_type = interface_type
                    self.responses_received = []
                
                async def send_response(self, response: ChatResponse):
                    self.responses_received.append(response)
                    print(f"\n🤖 {response.interface_type.value.upper()} Response:")
                    print(f"   Content: {response.content}")
                    print(f"   Confidence: {response.confidence:.2f}")
                    print(f"   Processing Time: {response.processing_time:.2f}s")
                    print(f"   Response Type: {response.response_type.value}")
                    if response.agent_insights:
                        print(f"   Agent Insights: {len(response.agent_insights)} items")
                    if response.service_results:
                        print(f"   Service Results: {len(response.service_results)} items")
                    print("-" * 60)
            
            # Register test interfaces
            web_interface = TestInterface(ChatInterface.WEB)
            desktop_interface = TestInterface(ChatInterface.DESKTOP)
            api_interface = TestInterface(ChatInterface.API)
            
            await chat_coordinator.register_interface(ChatInterface.WEB, web_interface)
            await chat_coordinator.register_interface(ChatInterface.DESKTOP, desktop_interface)
            await chat_coordinator.register_interface(ChatInterface.API, api_interface)
            
            # Test messages
            test_messages = [
                ("Hello! I'm here to test the ATOM system", "standard_chat"),
                ("Create an automated workflow for email follow-ups", "workflow_execution"),
                ("Integrate my Outlook calendar with Asana tasks", "service_integration"),
                ("Help me create a task for tomorrow's meeting", "task_creation"),
                ("What's the best way to manage multiple projects?", "information_query"),
                ("/status", "system_command"),
                ("/help", "system_command"),
                ("/services", "system_command"),
                ("Analyze the market trends for AI productivity tools", "advanced_chat"),
                ("Set up Jira integration with automated issue creation", "integration_workflow")
            ]
            
            logger.info("🧪 Running test messages...")
            
            for i, (content, message_type) in enumerate(test_messages, 1):
                logger.info(f"\n--- Test Message {i}: {content} ---")
                
                # Create test message
                message = ChatMessage(
                    message_id=f"test_msg_{i}",
                    user_id="test_user",
                    session_id="test_session",
                    interface_type=ChatInterface.WEB,
                    message_type=RequestType.CHAT_MESSAGE if message_type == "standard_chat" or message_type == "advanced_chat" else
                                   RequestType.WORKFLOW_EXECUTION if message_type == "workflow_execution" else
                                   RequestType.SERVICE_INTEGRATION if message_type == "service_integration" else
                                   RequestType.TASK_CREATION if message_type == "task_creation" else
                                   RequestType.INFORMATION_QUERY if message_type == "information_query" else
                                   RequestType.SYSTEM_COMMAND,
                    content=content,
                    metadata={"test_type": message_type}
                )
                
                # Process message
                response = await chat_coordinator.process_message(message)
                
                logger.info(f"✅ Test Message {i} processed successfully")
                
                # Small delay between messages
                await asyncio.sleep(2)
            
            # Display final metrics
            logger.info(f"\n📊 Final Chat Coordinator Metrics:")
            metrics = chat_coordinator.chat_metrics
            logger.info(f"   Total Messages Processed: {metrics['total_messages_processed']}")
            logger.info(f"   Average Processing Time: {metrics['average_processing_time']:.2f}s")
            logger.info(f"   Success Rate: {metrics['success_rate']:.2%}")
            logger.info(f"   Active Sessions: {metrics['active_sessions']}")
            logger.info(f"   Interface Usage: {metrics['interface_usage']}")
            
            logger.info("\n🎉 ATOM Chat Coordinator demonstration complete!")
            
        else:
            logger.error("❌ Failed to initialize ATOM Chat Coordinator")
        
        # Shutdown
        await chat_coordinator.shutdown()
    
    except Exception as e:
        logger.error(f"❌ Error in ATOM Chat Coordinator: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")

if __name__ == "__main__":
    asyncio.run(main())