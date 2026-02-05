import asyncio
from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
import uvicorn

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class WebSocketConnectionManager:
    """Manages WebSocket connections and real-time communication"""

    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.user_rooms: Dict[str, List[str]] = {}  # user_id -> room_ids
        self.room_connections: Dict[str, List[str]] = {}  # room_id -> user_ids
        self.user_data: Dict[str, Dict] = {}  # user_id -> user_data

    async def connect(self, websocket: WebSocket, user_id: str):
        """Accept WebSocket connection and add to active connections"""
        await websocket.accept()
        self.active_connections[user_id] = websocket

        # Initialize user data if not exists
        if user_id not in self.user_data:
            self.user_data[user_id] = {
                "connected_at": datetime.now().isoformat(),
                "last_activity": datetime.now().isoformat(),
                "rooms": [],
                "status": "online",
            }

        logger.info(f"User {user_id} connected to WebSocket server")

    def disconnect(self, user_id: str):
        """Remove user from active connections"""
        if user_id in self.active_connections:
            del self.active_connections[user_id]

            # Remove user from all rooms
            if user_id in self.user_rooms:
                for room_id in self.user_rooms[user_id]:
                    if room_id in self.room_connections:
                        if user_id in self.room_connections[room_id]:
                            self.room_connections[room_id].remove(user_id)
                del self.user_rooms[user_id]

            # Update user status
            if user_id in self.user_data:
                self.user_data[user_id]["status"] = "offline"
                self.user_data[user_id]["disconnected_at"] = datetime.now().isoformat()

            logger.info(f"User {user_id} disconnected from WebSocket server")

    async def send_personal_message(self, message: Dict[str, Any], user_id: str):
        """Send message to specific user"""
        if user_id in self.active_connections:
            try:
                await self.active_connections[user_id].send_json(message)
                return True
            except Exception as e:
                logger.error(f"Failed to send message to user {user_id}: {e}")
                self.disconnect(user_id)
                return False
        return False

    async def broadcast_to_room(
        self, message: Dict[str, Any], room_id: str, exclude_user: Optional[str] = None
    ):
        """Broadcast message to all users in a room"""
        if room_id not in self.room_connections:
            return 0

        sent_count = 0
        for user_id in self.room_connections[room_id]:
            if user_id != exclude_user:
                if await self.send_personal_message(message, user_id):
                    sent_count += 1

        logger.info(f"Broadcasted message to {sent_count} users in room {room_id}")
        return sent_count

    async def join_room(self, user_id: str, room_id: str):
        """Add user to a room"""
        if user_id not in self.user_rooms:
            self.user_rooms[user_id] = []

        if room_id not in self.room_connections:
            self.room_connections[room_id] = []

        if room_id not in self.user_rooms[user_id]:
            self.user_rooms[user_id].append(room_id)

        if user_id not in self.room_connections[room_id]:
            self.room_connections[room_id].append(user_id)

        # Notify room about new user
        await self.broadcast_to_room(
            {
                "type": "user_joined",
                "room_id": room_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
            room_id,
            exclude_user=user_id,
        )

        logger.info(f"User {user_id} joined room {room_id}")

    async def leave_room(self, user_id: str, room_id: str):
        """Remove user from a room"""
        if user_id in self.user_rooms and room_id in self.user_rooms[user_id]:
            self.user_rooms[user_id].remove(room_id)

        if (
            room_id in self.room_connections
            and user_id in self.room_connections[room_id]
        ):
            self.room_connections[room_id].remove(user_id)

        # Notify room about user leaving
        await self.broadcast_to_room(
            {
                "type": "user_left",
                "room_id": room_id,
                "user_id": user_id,
                "timestamp": datetime.now().isoformat(),
            },
            room_id,
            exclude_user=user_id,
        )

        logger.info(f"User {user_id} left room {room_id}")

    def get_user_status(self, user_id: str) -> Dict[str, Any]:
        """Get user connection status and data"""
        if user_id in self.user_data:
            status_data = self.user_data[user_id].copy()
            status_data["is_online"] = user_id in self.active_connections
            status_data["rooms"] = self.user_rooms.get(user_id, [])
            return status_data
        return {"is_online": False, "status": "unknown"}

    def get_room_info(self, room_id: str) -> Dict[str, Any]:
        """Get information about a room"""
        if room_id in self.room_connections:
            return {
                "room_id": room_id,
                "user_count": len(self.room_connections[room_id]),
                "users": self.room_connections[room_id],
                "online_users": [
                    uid
                    for uid in self.room_connections[room_id]
                    if uid in self.active_connections
                ],
            }
        return {"room_id": room_id, "user_count": 0, "users": [], "online_users": []}

    def get_server_stats(self) -> Dict[str, Any]:
        """Get WebSocket server statistics"""
        return {
            "active_connections": len(self.active_connections),
            "total_users": len(self.user_data),
            "total_rooms": len(self.room_connections),
            "online_users": [
                uid for uid in self.user_data if uid in self.active_connections
            ],
        }


# Initialize FastAPI app
app = FastAPI(
    title="ATOM WebSocket Server",
    description="Real-time WebSocket Communication for Chat Interface",
    version="1.0.0",
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:5173",
        "http://localhost:8000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize connection manager
manager = WebSocketConnectionManager()


# WebSocket endpoint for real-time chat
@app.websocket("/ws/{user_id}")
async def websocket_endpoint(websocket: WebSocket, user_id: str):
    """Main WebSocket endpoint for real-time communication"""
    await manager.connect(websocket, user_id)

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_text()
            message_data = json.loads(data)

            # Update user activity
            if user_id in manager.user_data:
                manager.user_data[user_id]["last_activity"] = datetime.now().isoformat()

            # Handle different message types
            message_type = message_data.get("type", "unknown")

            if message_type == "chat_message":
                # Handle chat message
                room_id = message_data.get("room_id", "general")
                message_content = message_data.get("message", "")

                # Broadcast message to room
                await manager.broadcast_to_room(
                    {
                        "type": "chat_message",
                        "room_id": room_id,
                        "user_id": user_id,
                        "message": message_content,
                        "timestamp": datetime.now().isoformat(),
                    },
                    room_id,
                    exclude_user=user_id,
                )

            elif message_type == "join_room":
                # Handle room join request
                room_id = message_data.get("room_id", "general")
                await manager.join_room(user_id, room_id)

                # Send confirmation to user
                await manager.send_personal_message(
                    {
                        "type": "room_joined",
                        "room_id": room_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                    user_id,
                )

            elif message_type == "leave_room":
                # Handle room leave request
                room_id = message_data.get("room_id", "general")
                await manager.leave_room(user_id, room_id)

                # Send confirmation to user
                await manager.send_personal_message(
                    {
                        "type": "room_left",
                        "room_id": room_id,
                        "timestamp": datetime.now().isoformat(),
                    },
                    user_id,
                )

            elif message_type == "typing_indicator":
                # Handle typing indicator
                room_id = message_data.get("room_id", "general")
                is_typing = message_data.get("is_typing", False)

                await manager.broadcast_to_room(
                    {
                        "type": "typing_indicator",
                        "room_id": room_id,
                        "user_id": user_id,
                        "is_typing": is_typing,
                        "timestamp": datetime.now().isoformat(),
                    },
                    room_id,
                    exclude_user=user_id,
                )

            elif message_type == "ping":
                # Handle ping/pong for connection health
                await manager.send_personal_message(
                    {"type": "pong", "timestamp": datetime.now().isoformat()}, user_id
                )

            else:
                logger.warning(
                    f"Unknown message type from user {user_id}: {message_type}"
                )

    except WebSocketDisconnect:
        manager.disconnect(user_id)
    except Exception as e:
        logger.error(f"WebSocket error for user {user_id}: {e}")
        manager.disconnect(user_id)


# HTTP endpoints for WebSocket management
@app.get("/")
async def root():
    return {"message": "ATOM WebSocket Server is running", "status": "operational"}


@app.get("/health")
async def health_check():
    stats = manager.get_server_stats()
    return {"status": "healthy", "version": "1.0.0", "server_stats": stats}


@app.get("/api/v1/websocket/users/{user_id}/status")
async def get_user_status(user_id: str):
    """Get user connection status"""
    return manager.get_user_status(user_id)


@app.get("/api/v1/websocket/rooms/{room_id}")
async def get_room_info(room_id: str):
    """Get room information"""
    return manager.get_room_info(room_id)


@app.get("/api/v1/websocket/stats")
async def get_server_stats():
    """Get WebSocket server statistics"""
    return manager.get_server_stats()


@app.post("/api/v1/websocket/users/{user_id}/message")
async def send_user_message(user_id: str, message: Dict[str, Any]):
    """Send message to specific user via HTTP"""
    success = await manager.send_personal_message(message, user_id)
    return {"success": success, "user_id": user_id}


@app.post("/api/v1/websocket/rooms/{room_id}/broadcast")
async def broadcast_to_room(room_id: str, message: Dict[str, Any]):
    """Broadcast message to room via HTTP"""
    sent_count = await manager.broadcast_to_room(message, room_id)
    return {"success": True, "sent_count": sent_count, "room_id": room_id}


# Background task for connection health monitoring
async def connection_health_monitor():
    """Monitor connection health and clean up stale connections"""
    while True:
        try:
            current_time = datetime.now()
            stale_users = []

            # Check for stale connections (no activity for 5 minutes)
            for user_id, user_data in manager.user_data.items():
                last_activity = datetime.fromisoformat(user_data["last_activity"])
                time_diff = (current_time - last_activity).total_seconds()

                if time_diff > 300:  # 5 minutes
                    stale_users.append(user_id)

            # Clean up stale users
            for user_id in stale_users:
                if user_id in manager.active_connections:
                    manager.disconnect(user_id)
                    logger.info(f"Cleaned up stale connection for user {user_id}")

            # Send periodic health check to all connections
            for user_id in list(manager.active_connections.keys()):
                await manager.send_personal_message(
                    {"type": "health_check", "timestamp": current_time.isoformat()},
                    user_id,
                )

        except Exception as e:
            logger.error(f"Error in connection health monitor: {e}")

        await asyncio.sleep(60)  # Check every minute


@app.on_event("startup")
async def startup_event():
    """Initialize services on startup"""
    logger.info("Starting ATOM WebSocket Server")
    # Start background health monitoring
    asyncio.create_task(connection_health_monitor())


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Shutting down ATOM WebSocket Server")
    # Disconnect all active connections
    for user_id in list(manager.active_connections.keys()):
        manager.disconnect(user_id)


if __name__ == "__main__":
    uvicorn.run(
        "websocket_server:app", host="0.0.0.0", port=5060, reload=True, log_level="info"
    )
