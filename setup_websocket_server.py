#!/usr/bin/env python3
"""
Setup WebSocket Server for Real-Time Features

This script implements:
- WebSocket server for real-time communication
- Client-side WebSocket management
- Real-time event handling and broadcasting
- Connection management and reconnection logic
- Live status updates for workflows
"""

import os
import sys
import logging
import json
import uuid
import asyncio
import time
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional, Set, Callable
from dataclasses import dataclass, field
from enum import Enum
import websockets
from websockets.server import WebSocketServerProtocol
import threading
from collections import defaultdict

# Add backend directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Import our working systems
from working_enhanced_workflow_engine import working_enhanced_workflow_engine

logger = logging.getLogger(__name__)


class WebSocketEventType(Enum):
    """WebSocket event types"""
    WORKFLOW_UPDATE = "workflow_update"
    EXECUTION_STATUS = "execution_status"
    SERVICE_STATUS = "service_status"
    NOTIFICATION = "notification"
    COLLABORATION = "collaboration"
    SYSTEM_UPDATE = "system_update"
    USER_ACTIVITY = "user_activity"
    ERROR = "error"
    HEARTBEAT = "heartbeat"


class ConnectionState(Enum):
    """WebSocket connection state"""
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTING = "disconnecting"
    DISCONNECTED = "disconnected"
    RECONNECTING = "reconnecting"
    ERROR = "error"


@dataclass
class WebSocketConnection:
    """WebSocket connection information"""
    connection_id: str
    websocket: WebSocketServerProtocol
    user_id: str
    session_id: Optional[str] = None
    connected_at: datetime = field(default_factory=datetime.now)
    last_activity: datetime = field(default_factory=datetime.now)
    subscriptions: Set[str] = field(default_factory=set)
    state: ConnectionState = ConnectionState.CONNECTED
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class WebSocketEvent:
    """WebSocket event message"""
    event_id: str
    event_type: WebSocketEventType
    payload: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    target_connections: List[str] = field(default_factory=list)
    broadcast: bool = False


class RealTimeWebSocketServer:
    """Real-time WebSocket server for workflow updates"""
    
    def __init__(self, host: str = "localhost", port: int = 8765):
        self.host = host
        self.port = port
        self.connections: Dict[str, WebSocketConnection] = {}
        self.user_connections: Dict[str, Set[str]] = defaultdict(set)  # user_id -> connection_ids
        self.session_connections: Dict[str, Set[str]] = defaultdict(set)  # session_id -> connection_ids
        self.subscriptions: Dict[str, Set[str]] = defaultdict(set)  # subscription -> connection_ids
        
        self.server = None
        self.running = False
        self.event_handlers = {}
        self.connection_handlers = {}
        
        # Performance metrics
        self.metrics = {
            "total_connections": 0,
            "active_connections": 0,
            "events_sent": 0,
            "events_received": 0,
            "errors": 0,
            "start_time": None
        }
        
        # Initialize event handlers
        self._initialize_event_handlers()
        self._initialize_connection_handlers()
    
    def _initialize_event_handlers(self):
        """Initialize WebSocket event handlers"""
        self.event_handlers = {
            WebSocketEventType.WORKFLOW_UPDATE: self._handle_workflow_update,
            WebSocketEventType.EXECUTION_STATUS: self._handle_execution_status,
            WebSocketEventType.SERVICE_STATUS: self._handle_service_status,
            WebSocketEventType.NOTIFICATION: self._handle_notification,
            WebSocketEventType.COLLABORATION: self._handle_collaboration,
            WebSocketEventType.SYSTEM_UPDATE: self._handle_system_update,
            WebSocketEventType.USER_ACTIVITY: self._handle_user_activity,
            WebSocketEventType.ERROR: self._handle_error,
            WebSocketEventType.HEARTBEAT: self._handle_heartbeat
        }
        
        logger.info(f"Initialized {len(self.event_handlers)} event handlers")
    
    def _initialize_connection_handlers(self):
        """Initialize connection lifecycle handlers"""
        self.connection_handlers = {
            "on_connect": self._on_connect,
            "on_disconnect": self._on_disconnect,
            "on_message": self._on_message,
            "on_error": self._on_error
        }
        
        logger.info("Initialized connection handlers")
    
    async def start_server(self):
        """Start the WebSocket server"""
        try:
            logger.info(f"Starting WebSocket server on {self.host}:{self.port}")
            
            self.running = True
            self.metrics["start_time"] = datetime.now()
            
            # Start WebSocket server
            self.server = await websockets.serve(
                self._handle_connection,
                self.host,
                self.port,
                ping_interval=20,
                ping_timeout=10,
                close_timeout=10,
                max_size=10_000_000,  # 10MB max message size
                max_queue=1000  # Max 1000 queued messages
            )
            
            logger.info(f"WebSocket server started successfully on ws://{self.host}:{self.port}")
            
            # Start background tasks
            asyncio.create_task(self._heartbeat_monitor())
            asyncio.create_task(self._cleanup_connections())
            asyncio.create_task(self._performance_monitor())
            
        except Exception as e:
            logger.error(f"Failed to start WebSocket server: {str(e)}")
            self.running = False
            raise
    
    async def stop_server(self):
        """Stop the WebSocket server"""
        try:
            logger.info("Stopping WebSocket server...")
            
            self.running = False
            
            # Close all connections
            for connection_id, connection in list(self.connections.items()):
                try:
                    await connection.websocket.close()
                except:
                    pass
            
            # Stop the server
            if self.server:
                self.server.close()
                await self.server.wait_closed()
            
            logger.info("WebSocket server stopped successfully")
            
        except Exception as e:
            logger.error(f"Error stopping WebSocket server: {str(e)}")
    
    async def _handle_connection(self, websocket: WebSocketServerProtocol, path: str):
        """Handle new WebSocket connection"""
        connection_id = str(uuid.uuid4())
        connection = WebSocketConnection(
            connection_id=connection_id,
            websocket=websocket,
            user_id="",  # Will be set during authentication
            session_id=None,
            state=ConnectionState.CONNECTING
        )
        
        try:
            # Add to connections
            self.connections[connection_id] = connection
            self.metrics["total_connections"] += 1
            self.metrics["active_connections"] = len(self.connections)
            
            logger.info(f"New WebSocket connection: {connection_id} from {path}")
            
            # Wait for authentication message
            auth_message = await websocket.recv()
            auth_data = json.loads(auth_message)
            
            # Validate authentication
            if auth_data.get("type") == "auth" and auth_data.get("user_id"):
                connection.user_id = auth_data["user_id"]
                connection.session_id = auth_data.get("session_id")
                connection.metadata.update(auth_data.get("metadata", {}))
                connection.state = ConnectionState.CONNECTED
                
                # Add to user and session mappings
                self.user_connections[connection.user_id].add(connection_id)
                if connection.session_id:
                    self.session_connections[connection.session_id].add(connection_id)
                
                # Send authentication success
                await self._send_to_connection(connection_id, {
                    "type": "auth_success",
                    "connection_id": connection_id,
                    "timestamp": datetime.now().isoformat()
                })
                
                # Call connection handler
                await self.connection_handlers["on_connect"](connection)
                
                logger.info(f"WebSocket {connection_id} authenticated for user {connection.user_id}")
            else:
                # Authentication failed
                await websocket.close(1008, "Authentication failed")
                logger.warning(f"WebSocket {connection_id} authentication failed")
                return
            
            # Main message loop
            connection.state = ConnectionState.CONNECTED
            while connection.state == ConnectionState.CONNECTED and not websocket.closed:
                try:
                    # Set timeout for receiving messages
                    message = await asyncio.wait_for(websocket.recv(), timeout=30.0)
                    
                    # Update activity timestamp
                    connection.last_activity = datetime.now()
                    
                    # Parse and handle message
                    try:
                        data = json.loads(message)
                        await self.connection_handlers["on_message"](connection, data)
                        self.metrics["events_received"] += 1
                        
                    except json.JSONDecodeError:
                        logger.error(f"Invalid JSON from connection {connection_id}")
                        await self._send_error(connection_id, "Invalid message format")
                    
                except asyncio.TimeoutError:
                    # Check if connection is still alive with ping
                    try:
                        await websocket.ping()
                        connection.last_activity = datetime.now()
                    except:
                        break  # Connection is dead
                
                except websockets.exceptions.ConnectionClosed:
                    break
                
                except Exception as e:
                    logger.error(f"Error handling message from {connection_id}: {str(e)}")
                    await self._send_error(connection_id, f"Message handling error: {str(e)}")
            
        except Exception as e:
            logger.error(f"Error in WebSocket connection {connection_id}: {str(e)}")
            await self.connection_handlers["on_error"](connection, e)
        
        finally:
            # Cleanup connection
            await self._cleanup_connection(connection_id)
            logger.info(f"WebSocket connection {connection_id} closed")
    
    async def _cleanup_connection(self, connection_id: str):
        """Clean up closed connection"""
        try:
            if connection_id not in self.connections:
                return
            
            connection = self.connections[connection_id]
            connection.state = ConnectionState.DISCONNECTED
            
            # Remove from user and session mappings
            if connection.user_id:
                self.user_connections[connection.user_id].discard(connection_id)
                if not self.user_connections[connection.user_id]:
                    del self.user_connections[connection.user_id]
            
            if connection.session_id:
                self.session_connections[connection.session_id].discard(connection_id)
                if not self.session_connections[connection.session_id]:
                    del self.session_connections[connection.session_id]
            
            # Remove from subscriptions
            for subscription in connection.subscriptions:
                self.subscriptions[subscription].discard(connection_id)
                if not self.subscriptions[subscription]:
                    del self.subscriptions[subscription]
            
            # Remove from connections
            del self.connections[connection_id]
            self.metrics["active_connections"] = len(self.connections)
            
            # Call disconnect handler
            await self.connection_handlers["on_disconnect"](connection)
            
        except Exception as e:
            logger.error(f"Error cleaning up connection {connection_id}: {str(e)}")
    
    async def _send_to_connection(self, connection_id: str, data: Dict[str, Any]):
        """Send message to specific connection"""
        try:
            if connection_id not in self.connections:
                logger.warning(f"Attempted to send to unknown connection: {connection_id}")
                return False
            
            connection = self.connections[connection_id]
            if connection.websocket.closed:
                return False
            
            message = json.dumps(data)
            await connection.websocket.send(message)
            self.metrics["events_sent"] += 1
            return True
            
        except Exception as e:
            logger.error(f"Error sending to connection {connection_id}: {str(e)}")
            return False
    
    async def _send_error(self, connection_id: str, error_message: str):
        """Send error message to connection"""
        error_data = {
            "type": "error",
            "error": error_message,
            "timestamp": datetime.now().isoformat()
        }
        await self._send_to_connection(connection_id, error_data)
    
    # Connection Handlers
    async def _on_connect(self, connection: WebSocketConnection):
        """Handle new connection"""
        try:
            logger.info(f"Connection established: {connection.connection_id} for user {connection.user_id}")
            
            # Send initial status
            await self._send_to_connection(connection.connection_id, {
                "type": "connection_established",
                "connection_id": connection.connection_id,
                "timestamp": datetime.now().isoformat(),
                "features": [
                    "workflow_updates",
                    "execution_status",
                    "collaboration",
                    "notifications"
                ]
            })
            
            # Subscribe user to default channels
            await self._subscribe_to_channel(connection.connection_id, f"user:{connection.user_id}")
            if connection.session_id:
                await self._subscribe_to_channel(connection.connection_id, f"session:{connection.session_id}")
            
        except Exception as e:
            logger.error(f"Error in connect handler: {str(e)}")
    
    async def _on_disconnect(self, connection: WebSocketConnection):
        """Handle connection disconnection"""
        try:
            logger.info(f"Connection disconnected: {connection.connection_id}")
            
            # Broadcast user activity
            await self._broadcast_event(WebSocketEvent(
                event_id=str(uuid.uuid4()),
                event_type=WebSocketEventType.USER_ACTIVITY,
                payload={
                    "user_id": connection.user_id,
                    "activity": "disconnected",
                    "timestamp": datetime.now().isoformat()
                },
                user_id=connection.user_id,
                target_connections=list(self.user_connections.get(connection.user_id, [])),
                broadcast=False
            ))
            
        except Exception as e:
            logger.error(f"Error in disconnect handler: {str(e)}")
    
    async def _on_message(self, connection: WebSocketConnection, data: Dict[str, Any]):
        """Handle incoming message"""
        try:
            message_type = data.get("type")
            
            if message_type == "subscribe":
                # Subscribe to channel
                channel = data.get("channel")
                if channel:
                    await self._subscribe_to_channel(connection.connection_id, channel)
                    
            elif message_type == "unsubscribe":
                # Unsubscribe from channel
                channel = data.get("channel")
                if channel:
                    await self._unsubscribe_from_channel(connection.connection_id, channel)
                    
            elif message_type == "workflow_command":
                # Handle workflow command
                await self._handle_workflow_command(connection, data)
                
            elif message_type == "collaboration":
                # Handle collaboration event
                await self._handle_collaboration_message(connection, data)
                
            elif message_type == "ping":
                # Respond to ping with pong
                await self._send_to_connection(connection.connection_id, {
                    "type": "pong",
                    "timestamp": datetime.now().isoformat()
                })
                
            else:
                logger.warning(f"Unknown message type: {message_type}")
                
        except Exception as e:
            logger.error(f"Error handling message: {str(e)}")
    
    async def _on_error(self, connection: WebSocketConnection, error: Exception):
        """Handle connection error"""
        try:
            logger.error(f"Connection error for {connection.connection_id}: {str(error)}")
            self.metrics["errors"] += 1
            
        except Exception as e:
            logger.error(f"Error in error handler: {str(e)}")
    
    # Event Handlers
    async def _handle_workflow_update(self, event: WebSocketEvent):
        """Handle workflow update event"""
        try:
            # Broadcast to relevant users
            if event.user_id:
                target_connections = list(self.user_connections.get(event.user_id, []))
            else:
                target_connections = list(self.connections.keys())
            
            for connection_id in target_connections:
                await self._send_to_connection(connection_id, {
                    "type": "workflow_update",
                    "event_id": event.event_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling workflow update: {str(e)}")
    
    async def _handle_execution_status(self, event: WebSocketEvent):
        """Handle execution status event"""
        try:
            # Send to user who started the execution
            user_id = event.payload.get("user_id")
            if user_id:
                target_connections = list(self.user_connections.get(user_id, []))
                
                for connection_id in target_connections:
                    await self._send_to_connection(connection_id, {
                        "type": "execution_status",
                        "event_id": event.event_id,
                        "payload": event.payload,
                        "timestamp": event.timestamp.isoformat()
                    })
            
        except Exception as e:
            logger.error(f"Error handling execution status: {str(e)}")
    
    async def _handle_service_status(self, event: WebSocketEvent):
        """Handle service status event"""
        try:
            # Broadcast to all connected users
            for connection_id in self.connections.keys():
                await self._send_to_connection(connection_id, {
                    "type": "service_status",
                    "event_id": event.event_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling service status: {str(e)}")
    
    async def _handle_notification(self, event: WebSocketEvent):
        """Handle notification event"""
        try:
            # Send to specific user or session
            if event.user_id:
                target_connections = list(self.user_connections.get(event.user_id, []))
            elif event.session_id:
                target_connections = list(self.session_connections.get(event.session_id, []))
            else:
                target_connections = list(self.connections.keys())
            
            for connection_id in target_connections:
                await self._send_to_connection(connection_id, {
                    "type": "notification",
                    "event_id": event.event_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling notification: {str(e)}")
    
    async def _handle_collaboration(self, event: WebSocketEvent):
        """Handle collaboration event"""
        try:
            # Send to all users in the session
            if event.session_id:
                target_connections = list(self.session_connections.get(event.session_id, []))
                
                for connection_id in target_connections:
                    await self._send_to_connection(connection_id, {
                        "type": "collaboration",
                        "event_id": event.event_id,
                        "payload": event.payload,
                        "timestamp": event.timestamp.isoformat()
                    })
            
        except Exception as e:
            logger.error(f"Error handling collaboration: {str(e)}")
    
    async def _handle_system_update(self, event: WebSocketEvent):
        """Handle system update event"""
        try:
            # Broadcast to all connections
            for connection_id in self.connections.keys():
                await self._send_to_connection(connection_id, {
                    "type": "system_update",
                    "event_id": event.event_id,
                    "payload": event.payload,
                    "timestamp": event.timestamp.isoformat()
                })
                
        except Exception as e:
            logger.error(f"Error handling system update: {str(e)}")
    
    async def _handle_user_activity(self, event: WebSocketEvent):
        """Handle user activity event"""
        try:
            # Send to other users in the same session
            if event.session_id:
                target_connections = list(self.session_connections.get(event.session_id, []))
                
                for connection_id in target_connections:
                    # Don't send back to the same user
                    connection = self.connections.get(connection_id)
                    if connection and connection.user_id != event.user_id:
                        await self._send_to_connection(connection_id, {
                            "type": "user_activity",
                            "event_id": event.event_id,
                            "payload": event.payload,
                            "timestamp": event.timestamp.isoformat()
                        })
            
        except Exception as e:
            logger.error(f"Error handling user activity: {str(e)}")
    
    async def _handle_error(self, event: WebSocketEvent):
        """Handle error event"""
        try:
            # Send error to specific user if available
            if event.user_id:
                target_connections = list(self.user_connections.get(event.user_id, []))
                
                for connection_id in target_connections:
                    await self._send_to_connection(connection_id, {
                        "type": "error",
                        "event_id": event.event_id,
                        "payload": event.payload,
                        "timestamp": event.timestamp.isoformat()
                    })
            
        except Exception as e:
            logger.error(f"Error handling error event: {str(e)}")
    
    async def _handle_heartbeat(self, event: WebSocketEvent):
        """Handle heartbeat event"""
        try:
            # Respond with heartbeat to keep connection alive
            if event.user_id:
                target_connections = list(self.user_connections.get(event.user_id, []))
                
                for connection_id in target_connections:
                    await self._send_to_connection(connection_id, {
                        "type": "heartbeat_response",
                        "event_id": event.event_id,
                        "timestamp": event.timestamp.isoformat()
                    })
            
        except Exception as e:
            logger.error(f"Error handling heartbeat: {str(e)}")
    
    # Helper Methods
    async def _subscribe_to_channel(self, connection_id: str, channel: str):
        """Subscribe connection to channel"""
        try:
            if connection_id in self.connections:
                connection = self.connections[connection_id]
                connection.subscriptions.add(channel)
                self.subscriptions[channel].add(connection_id)
                
                await self._send_to_connection(connection_id, {
                    "type": "subscription_confirmed",
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Connection {connection_id} subscribed to {channel}")
                
        except Exception as e:
            logger.error(f"Error subscribing to channel: {str(e)}")
    
    async def _unsubscribe_from_channel(self, connection_id: str, channel: str):
        """Unsubscribe connection from channel"""
        try:
            if connection_id in self.connections:
                connection = self.connections[connection_id]
                connection.subscriptions.discard(channel)
                self.subscriptions[channel].discard(connection_id)
                
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]
                
                await self._send_to_connection(connection_id, {
                    "type": "unsubscription_confirmed",
                    "channel": channel,
                    "timestamp": datetime.now().isoformat()
                })
                
                logger.info(f"Connection {connection_id} unsubscribed from {channel}")
                
        except Exception as e:
            logger.error(f"Error unsubscribing from channel: {str(e)}")
    
    async def _handle_workflow_command(self, connection: WebSocketConnection, data: Dict[str, Any]):
        """Handle workflow command from client"""
        try:
            command = data.get("command")
            workflow_data = data.get("data", {})
            
            if command == "create_workflow":
                # Create new workflow
                result = working_enhanced_workflow_engine.create_workflow_from_template(
                    template_id=workflow_data.get("template_id"),
                    parameters=workflow_data.get("parameters", {}),
                    user_id=connection.user_id
                )
                
                await self._send_to_connection(connection.connection_id, {
                    "type": "workflow_command_response",
                    "command": command,
                    "success": result.get("success", False),
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                })
                
            elif command == "execute_workflow":
                # Execute workflow
                result = working_enhanced_workflow_engine.execute_workflow(
                    workflow_id=workflow_data.get("workflow_id"),
                    input_data=workflow_data.get("input_data", {})
                )
                
                if result.get("success"):
                    # Start monitoring execution status
                    execution_id = result.get("execution_id")
                    
                    # Broadcast execution start
                    await self._broadcast_event(WebSocketEvent(
                        event_id=str(uuid.uuid4()),
                        event_type=WebSocketEventType.EXECUTION_STATUS,
                        payload={
                            "execution_id": execution_id,
                            "status": "started",
                            "workflow_id": workflow_data.get("workflow_id"),
                            "user_id": connection.user_id
                        },
                        user_id=connection.user_id
                    ))
                
                await self._send_to_connection(connection.connection_id, {
                    "type": "workflow_command_response",
                    "command": command,
                    "success": result.get("success", False),
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                })
                
            elif command == "get_execution_status":
                # Get execution status
                execution_id = workflow_data.get("execution_id")
                result = working_enhanced_workflow_engine.get_execution_status(execution_id)
                
                await self._send_to_connection(connection.connection_id, {
                    "type": "workflow_command_response",
                    "command": command,
                    "success": result.get("success", False),
                    "data": result,
                    "timestamp": datetime.now().isoformat()
                })
                
            else:
                await self._send_error(connection.connection_id, f"Unknown command: {command}")
                
        except Exception as e:
            logger.error(f"Error handling workflow command: {str(e)}")
            await self._send_error(connection.connection_id, f"Command error: {str(e)}")
    
    async def _handle_collaboration_message(self, connection: WebSocketConnection, data: Dict[str, Any]):
        """Handle collaboration message"""
        try:
            collaboration_type = data.get("collaboration_type")
            message_data = data.get("data", {})
            
            # Create collaboration event
            event = WebSocketEvent(
                event_id=str(uuid.uuid4()),
                event_type=WebSocketEventType.COLLABORATION,
                payload={
                    "collaboration_type": collaboration_type,
                    "data": message_data,
                    "user_id": connection.user_id,
                    "session_id": connection.session_id
                },
                user_id=connection.user_id,
                session_id=connection.session_id
            )
            
            await self.event_handlers[WebSocketEventType.COLLABORATION](event)
            
        except Exception as e:
            logger.error(f"Error handling collaboration message: {str(e)}")
    
    async def _broadcast_event(self, event: WebSocketEvent):
        """Broadcast event to appropriate connections"""
        try:
            handler = self.event_handlers.get(event.event_type)
            if handler:
                await handler(event)
            else:
                logger.warning(f"No handler for event type: {event.event_type}")
                
        except Exception as e:
            logger.error(f"Error broadcasting event: {str(e)}")
    
    # Background Tasks
    async def _heartbeat_monitor(self):
        """Monitor connection heartbeats"""
        while self.running:
            try:
                await asyncio.sleep(60)  # Check every minute
                
                current_time = datetime.now()
                dead_connections = []
                
                for connection_id, connection in self.connections.items():
                    # Check if connection is dead (no activity for 5 minutes)
                    if (current_time - connection.last_activity).total_seconds() > 300:
                        dead_connections.append(connection_id)
                
                # Clean up dead connections
                for connection_id in dead_connections:
                    logger.warning(f"Cleaning up dead connection: {connection_id}")
                    await self._cleanup_connection(connection_id)
                
            except Exception as e:
                logger.error(f"Error in heartbeat monitor: {str(e)}")
    
    async def _cleanup_connections(self):
        """Periodic cleanup of connections"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                # Clean up empty subscription mappings
                empty_subscriptions = [
                    sub for sub, conns in self.subscriptions.items()
                    if not conns
                ]
                
                for sub in empty_subscriptions:
                    del self.subscriptions[sub]
                
                logger.debug(f"Cleaned up {len(empty_subscriptions)} empty subscriptions")
                
            except Exception as e:
                logger.error(f"Error in cleanup task: {str(e)}")
    
    async def _performance_monitor(self):
        """Monitor server performance"""
        while self.running:
            try:
                await asyncio.sleep(300)  # Every 5 minutes
                
                if self.metrics["start_time"]:
                    uptime = datetime.now() - self.metrics["start_time"]
                    
                    performance_report = {
                        "uptime_seconds": uptime.total_seconds(),
                        "total_connections": self.metrics["total_connections"],
                        "active_connections": len(self.connections),
                        "events_sent": self.metrics["events_sent"],
                        "events_received": self.metrics["events_received"],
                        "errors": self.metrics["errors"],
                        "avg_events_per_minute": (
                            self.metrics["events_sent"] / max(uptime.total_seconds() / 60, 1)
                        )
                    }
                    
                    logger.info(f"WebSocket Server Performance: {performance_report}")
                    
                    # Broadcast performance to admin users
                    await self._broadcast_event(WebSocketEvent(
                        event_id=str(uuid.uuid4()),
                        event_type=WebSocketEventType.SYSTEM_UPDATE,
                        payload={
                            "type": "performance_report",
                            "data": performance_report
                        },
                        broadcast=True
                    ))
                
            except Exception as e:
                logger.error(f"Error in performance monitor: {str(e)}")
    
    # Public API Methods
    async def send_notification(self, user_id: str, message: str, notification_type: str = "info"):
        """Send notification to specific user"""
        try:
            event = WebSocketEvent(
                event_id=str(uuid.uuid4()),
                event_type=WebSocketEventType.NOTIFICATION,
                payload={
                    "message": message,
                    "type": notification_type,
                    "user_id": user_id
                },
                user_id=user_id
            )
            
            await self._broadcast_event(event)
            
        except Exception as e:
            logger.error(f"Error sending notification: {str(e)}")
    
    async def broadcast_workflow_update(self, user_id: str, workflow_id: str, update_data: Dict[str, Any]):
        """Broadcast workflow update to user"""
        try:
            event = WebSocketEvent(
                event_id=str(uuid.uuid4()),
                event_type=WebSocketEventType.WORKFLOW_UPDATE,
                payload={
                    "workflow_id": workflow_id,
                    "user_id": user_id,
                    "update": update_data
                },
                user_id=user_id
            )
            
            await self._broadcast_event(event)
            
        except Exception as e:
            logger.error(f"Error broadcasting workflow update: {str(e)}")
    
    async def broadcast_execution_status(self, user_id: str, execution_id: str, status: str, details: Dict[str, Any] = None):
        """Broadcast execution status update"""
        try:
            event = WebSocketEvent(
                event_id=str(uuid.uuid4()),
                event_type=WebSocketEventType.EXECUTION_STATUS,
                payload={
                    "execution_id": execution_id,
                    "status": status,
                    "user_id": user_id,
                    "details": details or {}
                },
                user_id=user_id
            )
            
            await self._broadcast_event(event)
            
        except Exception as e:
            logger.error(f"Error broadcasting execution status: {str(e)}")
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get server performance metrics"""
        uptime = None
        if self.metrics["start_time"]:
            uptime = datetime.now() - self.metrics["start_time"]
        
        return {
            "server_running": self.running,
            "uptime_seconds": uptime.total_seconds() if uptime else 0,
            "total_connections": self.metrics["total_connections"],
            "active_connections": len(self.connections),
            "events_sent": self.metrics["events_sent"],
            "events_received": self.metrics["events_received"],
            "errors": self.metrics["errors"],
            "subscriptions": len(self.subscriptions),
            "avg_events_per_minute": (
                self.metrics["events_sent"] / max(uptime.total_seconds() / 60, 1) if uptime else 0
            ),
            "memory_usage": len(self.connections) * 1024,  # Rough estimate
            "host": self.host,
            "port": self.port
        }


# Global WebSocket server instance
websocket_server = RealTimeWebSocketServer()

logger.info("Real-Time WebSocket Server initialized")


def start_websocket_server():
    """Start WebSocket server in background"""
    try:
        # Start server
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        
        # Run server
        loop.run_until_complete(websocket_server.start_server())
        loop.run_forever()
        
    except Exception as e:
        logger.error(f"Error starting WebSocket server: {str(e)}")


# Start WebSocket server in background thread
websocket_thread = threading.Thread(target=start_websocket_server, daemon=True)
websocket_thread.start()

logger.info("WebSocket server background thread started")