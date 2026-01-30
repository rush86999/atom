"""
Completely standalone test server for testing streaming and canvas implementation.
No dependencies on existing backend infrastructure.
"""

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Dict, Any
import uuid
import asyncio
import json

# Create FastAPI app
app = FastAPI(title="Atom Implementation Test Server")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Simple connection manager for testing
class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, List[WebSocket]] = {}
        self.user_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, token: str):
        await websocket.accept()
        user_id = "dev-user"
        self.user_connections[user_id] = self.user_connections.get(user_id, [])
        self.user_connections[user_id].append(websocket)
        self.subscribe(websocket, f"user:{user_id}")
        return type('User', (), {'id': user_id, 'email': 'dev@local'})()

    def disconnect(self, websocket: WebSocket, user_id: str):
        if user_id in self.user_connections and websocket in self.user_connections[user_id]:
            self.user_connections[user_id].remove(websocket)

    def subscribe(self, websocket: WebSocket, channel: str):
        if channel not in self.active_connections:
            self.active_connections[channel] = []
        if websocket not in self.active_connections[channel]:
            self.active_connections[channel].append(websocket)

    async def broadcast(self, channel: str, message: dict):
        if channel in self.active_connections:
            for connection in self.active_connections[channel][:]:
                try:
                    await connection.send_json(message)
                except:
                    pass

manager = ConnectionManager()

# Models
class ChatRequest(BaseModel):
    message: str
    user_id: str
    session_id: Optional[str] = None
    workspace_id: Optional[str] = None

class FormSubmission(BaseModel):
    canvas_id: str
    form_data: Dict[str, Any]

# Routes
@app.get("/")
async def root():
    return {
        "status": "ok",
        "message": "Atom Implementation Test Server",
        "features": ["streaming", "canvas", "forms"]
    }

@app.get("/health")
async def health():
    return {"status": "healthy", "implementation": "All 3 phases"}

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for testing streaming and canvas"""
    user = await manager.connect(websocket, token="dev-token")
    print(f"✓ User {user.id} connected")

    try:
        while True:
            data = await websocket.receive_text()
            message = json.loads(data)

            # Handle subscription
            if message.get("type") == "subscribe":
                manager.subscribe(websocket, message.get("channel"))
                print(f"✓ User {user.id} subscribed to {message.get('channel')}")

    except WebSocketDisconnect:
        manager.disconnect(websocket, user.id)
        print(f"✗ User {user.id} disconnected")
    except Exception as e:
        print(f"WebSocket error: {e}")

# Phase 1: Streaming endpoint
@app.post("/api/atom-agent/chat/stream")
async def chat_stream(request: ChatRequest):
    """Test Phase 1: LLM Token Streaming"""
    message_id = str(uuid.uuid4())
    user_channel = f"user:{request.user_id}"

    # Simulate streaming a response token by token
    test_response = "This is a test of the streaming implementation! Tokens appear progressively as the LLM generates them. This provides a much better user experience compared to waiting for the complete response."

    # Send start message
    await manager.broadcast(user_channel, {
        "type": "streaming:start",
        "id": message_id,
        "model": "test-model",
        "provider": "test-provider"
    })

    # Stream tokens
    accumulated = ""
    words = test_response.split()
    for i, word in enumerate(words):
        await asyncio.sleep(0.05)  # Simulate token generation delay
        accumulated += word + " "
        await manager.broadcast(user_channel, {
            "type": "streaming:update",
            "id": message_id,
            "delta": word + " ",
            "complete": False,
            "metadata": {"tokens_so_far": len(accumulated)}
        })

    # Send completion
    await manager.broadcast(user_channel, {
        "type": "streaming:complete",
        "id": message_id,
        "content": accumulated.strip(),
        "complete": True
    })

    return {
        "success": True,
        "message_id": message_id,
        "streamed": True
    }

# Phase 3: Form submission endpoint
@app.post("/api/canvas/submit")
async def submit_form(submission: FormSubmission):
    """Test Phase 3: Form Submission"""
    print(f"✓ Form submitted: {submission.canvas_id}")
    print(f"  Data: {submission.form_data}")

    # Broadcast form submission notification
    user_channel = "user:dev-user"  # Simplified for testing
    await manager.broadcast(user_channel, {
        "type": "canvas:form_submitted",
        "canvas_id": submission.canvas_id,
        "data": submission.form_data,
        "user_id": "dev-user"
    })

    return {
        "status": "success",
        "submission_id": str(uuid.uuid4()),
        "message": "Form submitted successfully"
    }

@app.get("/api/canvas/status")
async def canvas_status():
    """Canvas status endpoint"""
    return {
        "status": "active",
        "user_id": "dev-user",
        "features": ["markdown", "status_panel", "form", "line_chart", "bar_chart", "pie_chart"]
    }

# Test helper endpoints
@app.post("/test/present-chart")
async def test_present_chart(chart_type: str = "line_chart"):
    """Test helper to trigger chart presentation"""
    user_channel = "user:dev-user"

    test_data = {
        "line_chart": [
            {"timestamp": "10:00", "value": 100},
            {"timestamp": "11:00", "value": 150},
            {"timestamp": "12:00", "value": 130}
        ],
        "bar_chart": [
            {"name": "Q1", "value": 10000},
            {"name": "Q2", "value": 15000},
            {"name": "Q3", "value": 12000}
        ],
        "pie_chart": [
            {"name": "Product A", "value": 30},
            {"name": "Product B", "value": 50},
            {"name": "Product C", "value": 20}
        ]
    }

    await manager.broadcast(user_channel, {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": chart_type,
            "data": {
                "data": test_data.get(chart_type, test_data["line_chart"]),
                "title": f"Test {chart_type.replace('_', ' ').title()}"
            }
        }
    })

    return {"status": "sent", "chart_type": chart_type}

@app.post("/test/present-form")
async def test_present_form():
    """Test helper to trigger form presentation"""
    user_channel = "user:dev-user"

    await manager.broadcast(user_channel, {
        "type": "canvas:update",
        "data": {
            "action": "present",
            "component": "form",
            "data": {
                "title": "User Information Form",
                "submitLabel": "Submit Info",
                "fields": [
                    {
                        "name": "email",
                        "label": "Email Address",
                        "type": "email",
                        "required": True,
                        "validation": {
                            "pattern": "^[^@]+@[^@]+\\.[^@]+$",
                            "custom": "Invalid email format"
                        }
                    },
                    {
                        "name": "age",
                        "label": "Age",
                        "type": "number",
                        "required": True,
                        "validation": {"min": 18, "max": 120}
                    },
                    {
                        "name": "country",
                        "label": "Country",
                        "type": "select",
                        "options": [
                            {"value": "us", "label": "United States"},
                            {"value": "uk", "label": "United Kingdom"},
                            {"value": "ca", "label": "Canada"}
                        ]
                    },
                    {
                        "name": "newsletter",
                        "label": "Subscribe to newsletter",
                        "type": "checkbox"
                    }
                ]
            }
        }
    })

    return {"status": "sent", "component": "form"}

if __name__ == "__main__":
    print("\n" + "="*70)
    print(" "*15 + "ATOM IMPLEMENTATION TEST SERVER")
    print("="*70)
    print("\nTesting Features:")
    print("  ✓ Phase 1: LLM Token Streaming")
    print("  ✓ Phase 2: Canvas Chart Components")
    print("  ✓ Phase 3: Interactive Form System")
    print("\n" + "="*70)
    print("\nServer Info:")
    print("  HTTP:  http://localhost:8000")
    print("  WS:    ws://localhost:8000/ws?token=dev-token")
    print("  Docs:  http://localhost:8000/docs")
    print("\nTest Endpoints:")
    print("  POST /test/present-chart  - Trigger chart display")
    print("  POST /test/present-form   - Trigger form display")
    print("  POST /api/atom-agent/chat/stream - Test streaming")
    print("\n" + "="*70)
    print("\nStarting server...\n")

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
