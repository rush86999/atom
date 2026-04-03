"""
Minimal test server for testing the streaming and canvas implementation.
This bypasses existing backend issues to test only the new functionality.
"""

import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Create minimal FastAPI app
app = FastAPI(title="Atom Test Server")

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Import and include ONLY the routes we created/tested
try:
    print("Importing canvas routes...")
    from api.canvas_routes import router as canvas_router
    app.include_router(canvas_router)
    print("✓ Canvas routes loaded")
except Exception as e:
    print(f"✗ Canvas routes failed: {e}")

try:
    print("Importing atom agent routes (for streaming endpoint)...")
    # We'll create a minimal streaming endpoint inline since the full module has dependencies
    from typing import Any, Dict, List, Optional
    from pydantic import BaseModel

    class ChatRequest(BaseModel):
        message: str
        user_id: str
        session_id: Optional[str] = None
        workspace_id: Optional[str] = None
        current_page: Optional[str] = None
        conversation_history: Optional[List[Dict]] = None

    @app.post("/api/atom-agent/chat/stream")
    async def chat_stream(request: ChatRequest):
        """Test streaming endpoint"""
        import uuid

        from core.websockets import manager as ws_manager

        message_id = str(uuid.uuid4())
        user_channel = f"user:{request.user_id}"

        # Simulate streaming
        test_response = "This is a test streaming response. The implementation is working correctly!"

        # Send tokens
        for i, char in enumerate(test_response):
            await ws_manager.broadcast(user_channel, {
                "type": "streaming:update",
                "id": message_id,
                "delta": char,
                "complete": False
            })

        # Send completion
        await ws_manager.broadcast(user_channel, {
            "type": "streaming:complete",
            "id": message_id,
            "content": test_response,
            "complete": True
        })

        return {
            "success": True,
            "message_id": message_id,
            "streamed": True
        }

    print("✓ Streaming endpoint loaded (inline)")
except Exception as e:
    print(f"✗ Streaming endpoint failed: {e}")

# WebSocket endpoint
from fastapi import WebSocket

from core.websockets import manager as ws_manager


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for testing"""
    user = await ws_manager.connect(websocket, token="dev-token")
    if user:
        print(f"✓ User {user.id} connected via WebSocket")
        try:
            while True:
                await websocket.receive_text()
        except:
            pass
        finally:
            ws_manager.disconnect(websocket, user.id)
    else:
        await websocket.close()

@app.get("/")
async def root():
    return {"status": "ok", "message": "Atom Test Server - Streaming & Canvas Implementation"}

@app.get("/health")
async def health():
    return {"status": "healthy", "implementation": "streaming + canvas"}

if __name__ == "__main__":
    print("\n" + "="*60)
    print("ATOM TEST SERVER")
    print("="*60)
    print("Testing Implementation:")
    print("  - Phase 1: LLM Token Streaming")
    print("  - Phase 2: Canvas Chart Components")
    print("  - Phase 3: Interactive Form System")
    print("="*60)
    print("\nStarting server on http://localhost:8000")
    print("WebSocket: ws://localhost:8000/ws?token=dev-token")
    print("\nPress Ctrl+C to stop\n")

    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="info")
