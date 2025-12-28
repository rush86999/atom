import asyncio
import json
import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

import uvicorn
from fastapi import Depends, FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

# Import Phase 2 features
try:
    from basic_analytics import router as analytics_router
    from multimodal_chat_routes import router as multimodal_router
    from voice_integration_service import router as voice_router

    MULTIMODAL_AVAILABLE = True
    VOICE_AVAILABLE = True
    ANALYTICS_AVAILABLE = True
except ImportError as e:
    print(f"Phase 2 features not available: {e}")
    MULTIMODAL_AVAILABLE = False
    VOICE_AVAILABLE = False
    ANALYTICS_AVAILABLE = False
    multimodal_router = None
    voice_router = None
    analytics_router = None

# Import Enterprise services (lazy initialization to avoid event loop issues)
# Import Enterprise services
try:
    from enterprise_analytics_dashboard import router as enterprise_analytics_router
    from enterprise_directory_service import router as directory_router
    from enterprise_salesforce_connector import router as salesforce_router
    from enterprise_sso_service import router as sso_router

    ENTERPRISE_SSO_AVAILABLE = True
    ENTERPRISE_DIRECTORY_AVAILABLE = True
    ENTERPRISE_SALESFORCE_AVAILABLE = True
    ENTERPRISE_ANALYTICS_AVAILABLE = True
except ImportError as e:
    print(f"Enterprise services not available: {e}")
    ENTERPRISE_SSO_AVAILABLE = False
    ENTERPRISE_DIRECTORY_AVAILABLE = False
    ENTERPRISE_SALESFORCE_AVAILABLE = False
    ENTERPRISE_ANALYTICS_AVAILABLE = False
    sso_router = None
    directory_router = None
    salesforce_router = None
    enterprise_analytics_router = None

# Import Teams integration
try:
    from teams_fastapi_router import router as teams_router

    TEAMS_AVAILABLE = True
except ImportError as e:
    print(f"Teams integration not available: {e}")
    TEAMS_AVAILABLE = False
    teams_router = None

# Import ServiceNow integration
try:
    from servicenow_fastapi_router import router as servicenow_router

    SERVICENOW_AVAILABLE = True
except ImportError as e:
    print(f"ServiceNow integration not available: {e}")
    SERVICENOW_AVAILABLE = False
    servicenow_router = None

# Import MFA integration
try:
    from mfa_fastapi_router import router as mfa_router

    MFA_AVAILABLE = True
except ImportError as e:
    print(f"MFA integration not available: {e}")
    MFA_AVAILABLE = False
    mfa_router = None

# Import existing services
try:
    from database_manager import db_manager
    from integrations.atom_chat_interface import AtomChatInterface
    from monitoring_analytics_system import MonitoringAnalyticsSystem
except ImportError as e:
    print(f"Warning: Some dependencies not available: {e}")

    # Create mock classes for development
    class AtomChatInterface:
        def __init__(self):
            self.connected = True

        async def process_message(self, message, context):
            return {"response": f"Echo: {message}", "workflow_triggered": False}

    class DatabaseManager:
        async def create_user(self, email, name):
            return {"id": "test_user", "email": email, "name": name}

    class MonitoringAnalyticsSystem:
        def record_metric(self, *args, **kwargs):
            pass

    db_manager = DatabaseManager()
    monitoring_system = MonitoringAnalyticsSystem()

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Pydantic models for chat interface
class ChatMessage(BaseModel):
    message: str = Field(..., description="The chat message content")
    user_id: str = Field(..., description="User identifier")
    context_id: Optional[str] = Field(
        None, description="Conversation context identifier"
    )
    message_type: str = Field("text", description="Type of message (text, voice, file)")
    metadata: Optional[Dict[str, Any]] = Field(
        None, description="Additional message metadata"
    )


class ChatResponse(BaseModel):
    response: str = Field(..., description="The AI response")
    context_id: str = Field(..., description="Updated conversation context identifier")
    workflow_triggered: bool = Field(
        False, description="Whether a workflow was triggered"
    )
    workflow_id: Optional[str] = Field(None, description="ID of triggered workflow")
    suggestions: List[str] = Field(
        default_factory=list, description="Suggested follow-up actions"
    )
    timestamp: str = Field(..., description="Response timestamp")


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_contexts: Dict[str, Dict] = {}
        self.chat_interface = AtomChatInterface()
        self.monitoring_system = monitoring_system

    async def connect(self, websocket: WebSocket, user_id: str):
        await websocket.accept()
        self.active_connections[user_id] = websocket

        # Initialize user context if not exists
        if user_id not in self.user_contexts:
            self.user_contexts[user_id] = {
                "context_id": f"ctx_{user_id}_{datetime.now().isoformat()}",
                "conversation_history": [],
                "last_activity": datetime.now().isoformat(),
            }

        logger.info(f"User {user_id} connected to chat interface")
        self.monitoring_system.record_metric(
            "chat_connections", 1, tags={"user_id": user_id, "type": "connect"}
        )

    def disconnect(self, user_id: str):
        if user_id in self.active_connections:
            del self.active_connections[user_id]
            logger.info(f"User {user_id} disconnected from chat interface")
            self.monitoring_system.record_metric(
                "chat_connections", -1, tags={"user_id": user_id, "type": "disconnect"}
            )

    async def send_personal_message(self, message: str, user_id: str):
        if user_id in self.active_connections:
            await self.active_connections[user_id].send_text(message)

    async def broadcast(self, message: str):
        for connection in self.active_connections.values():
            await connection.send_text(message)

    async def process_chat_message(self, chat_message: ChatMessage) -> ChatResponse:
        try:
            # Get user context
            user_context = self.user_contexts.get(chat_message.user_id, {})
            context_id = user_context.get(
                "context_id", f"ctx_{chat_message.user_id}_{datetime.now().isoformat()}"
            )

            # Update conversation history
            user_context.setdefault("conversation_history", []).append(
                {
                    "role": "user",
                    "message": chat_message.message,
                    "timestamp": datetime.now().isoformat(),
                    "message_type": chat_message.message_type,
                }
            )

            # Process message through chat interface
            result = await self.chat_interface.process_message(
                chat_message.message,
                {
                    "user_id": chat_message.user_id,
                    "context_id": context_id,
                    "conversation_history": user_context["conversation_history"][
                        -10:
                    ],  # Last 10 messages
                    "metadata": chat_message.metadata or {},
                },
            )

            # Update context with AI response
            user_context["conversation_history"].append(
                {
                    "role": "assistant",
                    "message": result.get(
                        "response", "I'm sorry, I couldn't process that request."
                    ),
                    "timestamp": datetime.now().isoformat(),
                    "workflow_triggered": result.get("workflow_triggered", False),
                    "workflow_id": result.get("workflow_id"),
                }
            )

            # Keep only last 50 messages to prevent memory bloat
            if len(user_context["conversation_history"]) > 50:
                user_context["conversation_history"] = user_context[
                    "conversation_history"
                ][-50:]

            user_context["last_activity"] = datetime.now().isoformat()
            self.user_contexts[chat_message.user_id] = user_context

            # Record metrics
            self.monitoring_system.record_metric(
                "chat_messages_processed",
                1,
                tags={
                    "user_id": chat_message.user_id,
                    "workflow_triggered": result.get("workflow_triggered", False),
                },
            )

            return ChatResponse(
                response=result.get(
                    "response", "I'm sorry, I couldn't process that request."
                ),
                context_id=context_id,
                workflow_triggered=result.get("workflow_triggered", False),
                workflow_id=result.get("workflow_id"),
                suggestions=result.get("suggestions", []),
                timestamp=datetime.now().isoformat(),
            )

        except Exception as e:
            logger.error(f"Error processing chat message: {e}")
            self.monitoring_system.record_metric(
                "chat_errors",
                1,
                tags={"user_id": chat_message.user_id, "error_type": "processing"},
            )
            return ChatResponse(
                response="I'm sorry, I encountered an error processing your message. Please try again.",
                context_id=chat_message.context_id
                or f"ctx_{chat_message.user_id}_{datetime.now().isoformat()}",
                workflow_triggered=False,
                timestamp=datetime.now().isoformat(),
            )


# Initialize FastAPI app
app = FastAPI(
    title="ATOM Chat Interface API",
    description="Advanced Chat Interface with Workflow Integration",
    version="2.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize connection manager
manager = ConnectionManager()

# Include Phase 2 feature routes if available
if MULTIMODAL_AVAILABLE and multimodal_router:
    app.include_router(multimodal_router)
    print("✅ Multi-modal chat routes loaded")
else:
    print("⚠️  Multi-modal chat routes not available")

if VOICE_AVAILABLE and voice_router:
    app.include_router(voice_router)
    print("✅ Voice integration routes loaded")
else:
    print("⚠️  Voice integration routes not available")

if ANALYTICS_AVAILABLE and analytics_router:
    app.include_router(analytics_router)
    print("✅ Analytics dashboard routes loaded")
else:
    print("⚠️  Analytics dashboard routes not available")

# Include enterprise services (with lazy initialization)
if ENTERPRISE_SSO_AVAILABLE and sso_router:
    app.include_router(sso_router, prefix="/api/v1/enterprise/sso")
    print("✅ Enterprise SSO service loaded")
else:
    print("⚠️  Enterprise SSO service not available")

if ENTERPRISE_DIRECTORY_AVAILABLE and directory_router:
    app.include_router(directory_router, prefix="/api/v1/enterprise/directory")
    print("✅ Enterprise directory service loaded")
else:
    print("⚠️  Enterprise directory service not available")

if ENTERPRISE_SALESFORCE_AVAILABLE and salesforce_router:
    # Initialize Salesforce connector with lazy session creation
    try:
        from enterprise_salesforce_connector import (
            default_salesforce_config,
            enterprise_salesforce_connector,
        )

        # Initialize without creating session immediately
        enterprise_salesforce_connector.config = default_salesforce_config
        print(
            "✅ Enterprise Salesforce connector configured (session creation deferred)"
        )
    except Exception as e:
        print(f"⚠️  Salesforce connector configuration failed: {e}")

    app.include_router(salesforce_router, prefix="/api/v1/enterprise/salesforce")
    print("✅ Enterprise Salesforce connector loaded")
else:
    print("⚠️  Enterprise Salesforce connector not available")

if ENTERPRISE_ANALYTICS_AVAILABLE and enterprise_analytics_router:
    app.include_router(
        enterprise_analytics_router, prefix="/api/v1/enterprise/analytics"
    )
    print("✅ Enterprise analytics dashboard loaded")
else:
    print("⚠️  Enterprise analytics dashboard not available")

# Include Teams integration
if TEAMS_AVAILABLE and teams_router:
    app.include_router(teams_router, prefix="/api/v1/integrations")
    print("✅ Microsoft Teams integration loaded")
else:
    print("⚠️  Microsoft Teams integration not available")

# Include ServiceNow integration
if SERVICENOW_AVAILABLE and servicenow_router:
    app.include_router(servicenow_router, prefix="/api/v1/integrations")
    print("✅ ServiceNow integration loaded")
else:
    print("⚠️  ServiceNow integration not available")

# Include MFA integration
if MFA_AVAILABLE and mfa_router:
    app.include_router(mfa_router, prefix="/api/v1/security")
    print("✅ MFA integration loaded")
else:
    print("⚠️  MFA integration not available")


# HTTP endpoints
@app.get("/")
async def root():
    return {"message": "ATOM Chat Interface API is running", "status": "operational"}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    health_data = {
        "status": "healthy",
        "version": "2.0.0",
        "active_connections": len(manager.active_connections),
        "monitored_users": len(manager.user_contexts),
        "features": {
            "multimodal_chat": MULTIMODAL_AVAILABLE,
            "voice_integration": VOICE_AVAILABLE,
            "analytics": ANALYTICS_AVAILABLE,
            "enterprise_sso": ENTERPRISE_SSO_AVAILABLE,
            "enterprise_directory": ENTERPRISE_DIRECTORY_AVAILABLE,
            "enterprise_salesforce": ENTERPRISE_SALESFORCE_AVAILABLE,
            "enterprise_analytics": ENTERPRISE_ANALYTICS_AVAILABLE,
            "teams_integration": TEAMS_AVAILABLE,
            "servicenow_integration": SERVICENOW_AVAILABLE,
            "mfa_integration": MFA_AVAILABLE,
        },
    }

    # Check enterprise service health if available
    if ENTERPRISE_SSO_AVAILABLE:
        try:
            health_data["enterprise_sso_health"] = "available"
        except:
            health_data["enterprise_sso_health"] = "unavailable"

    if ENTERPRISE_DIRECTORY_AVAILABLE:
        try:
            health_data["enterprise_directory_health"] = "available"
        except:
            health_data["enterprise_directory_health"] = "unavailable"

    if ENTERPRISE_SALESFORCE_AVAILABLE:
        try:
            health_data["enterprise_salesforce_health"] = "available"
        except:
            health_data["enterprise_salesforce_health"] = "unavailable"

    return health_data


@app.get("/api/v1/chat/users/{user_id}/context")
async def get_user_context(user_id: str):
    """Get conversation context for a user"""
    if user_id not in manager.user_contexts:
        raise HTTPException(status_code=404, detail="User context not found")

    context = manager.user_contexts[user_id]
    # Return limited context for privacy
    return {
        "user_id": user_id,
        "context_id": context.get("context_id"),
        "last_activity": context.get("last_activity"),
        "conversation_length": len(context.get("conversation_history", [])),
        "recent_messages": context.get("conversation_history", [])[
            -5:
        ],  # Last 5 messages only
    }


@app.post("/api/v1/chat/message")
async def send_chat_message(chat_message: ChatMessage):
    """Send a chat message via HTTP (for non-WebSocket clients)"""
    response = await manager.process_chat_message(chat_message)

    # Record analytics if available
    if ANALYTICS_AVAILABLE:
        try:
            from analytics_dashboard import analytics_service

            await analytics_service.record_message(
                {
                    "user_id": chat_message.user_id,
                    "conversation_id": response.context_id,
                    "message_type": chat_message.message_type,
                    "response_time": 0.0,  # Would need to measure actual response time
                    "has_attachments": bool(
                        chat_message.metadata
                        and chat_message.metadata.get("attachments")
                    ),
                    "workflow_triggered": response.workflow_triggered,
                }
            )
        except Exception as e:
            logger.warning(f"Failed to record analytics: {e}")

    return response


@app.get("/api/v1/chat/connections")
async def get_active_connections():
    """Get information about active WebSocket connections"""
    return {
        "active_connections": len(manager.active_connections),
        "connected_users": list(manager.active_connections.keys()),
    }


@app.get("/api/v1/chat/features")
async def get_available_features():
    """Get information about available chat features"""
    return {
        "version": "2.0.0",
        "features": {
            "basic_chat": True,
            "websocket_realtime": True,
            "multimodal_chat": MULTIMODAL_AVAILABLE,
            "voice_integration": VOICE_AVAILABLE,
            "analytics_dashboard": ANALYTICS_AVAILABLE,
            "workflow_integration": True,
            "context_management": True,
        },
        "status": "operational",
    }


# WebSocket endpoint
@app.websocket("/ws/chat/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    await manager.connect(websocket, user_id)
    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Process chat message
            chat_message = ChatMessage(
                message=message_data.get("message", ""),
                user_id=user_id,
                context_id=message_data.get("context_id"),
                message_type=message_data.get("message_type", "text"),
                metadata=message_data.get("metadata"),
            )

            # Process and send response
            response = await manager.process_chat_message(chat_message)
            await websocket.send_text(response.json())

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id)


# Background tasks
@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting ATOM Chat Interface Server")
    # Initialize monitoring system if available
    try:
        manager.monitoring_system.start_monitoring()
        logger.info("Monitoring system started")
    except Exception as e:
        logger.warning(f"Could not start monitoring system: {e}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down ATOM Chat Interface Server")
    try:
        manager.monitoring_system.stop_monitoring()
        logger.info("Monitoring system stopped")
    except Exception as e:
        logger.warning(f"Could not stop monitoring system: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "chat_interface_server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info",
    )
