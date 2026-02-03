import asyncio
import logging
import json
from typing import Dict, Any, Optional
from fastapi import WebSocket, WebSocketDisconnect

logger = logging.getLogger(__name__)

class SatelliteService:
    """
    Manages WebSocket connections to Satellite CLI clients (Local Nodes).
    Routes tool execution requests from SaaS Agents to the user's local machine.
    """
    
    _instance = None
    
    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(SatelliteService, cls).__new__(cls)
            cls._instance.active_connections: Dict[str, WebSocket] = {} # tenant_id -> WebSocket
            cls._instance.pending_requests: Dict[str, asyncio.Future] = {} # request_id -> Future
        return cls._instance

    async def connect(self, websocket: WebSocket, tenant_id: str):
        """Register a new satellite connection."""
        await websocket.accept()
        self.active_connections[tenant_id] = websocket
        logger.info(f"Satellite connected for tenant: {tenant_id}")

    def disconnect(self, tenant_id: str):
        """Remove a satellite connection."""
        if tenant_id in self.active_connections:
            del self.active_connections[tenant_id]
            logger.info(f"Satellite disconnected for tenant: {tenant_id}")

    async def execute_local_tool(self, tenant_id: str, tool_name: str, arguments: Dict[str, Any]) -> Any:
        """
        Route a tool call to the connected satellite.
        Waits for the response.
        """
        if tenant_id not in self.active_connections:
            return {"error": "Satellite not connected. Run 'python atom_satellite.py' locally."}
            
        websocket = self.active_connections[tenant_id]
        request_id = f"{tenant_id}-{asyncio.get_event_loop().time()}"
        
        payload = {
            "type": "tool_call",
            "request_id": request_id,
            "tool": tool_name,
            "arguments": arguments
        }
        
        # Create a future to wait for the response
        loop = asyncio.get_running_loop()
        future = loop.create_future()
        self.pending_requests[request_id] = future
        
        try:
            await websocket.send_json(payload)
            
            # Wait for response with timeout
            response = await asyncio.wait_for(future, timeout=30.0)
            return response
            
        except asyncio.TimeoutError:
            return {"error": "Satellite request timed out."}
        except Exception as e:
            return {"error": f"Satellite communication error: {str(e)}"}
        finally:
            if request_id in self.pending_requests:
                del self.pending_requests[request_id]

    async def handle_message(self, tenant_id: str, message: Dict[str, Any]):
        """Process incoming messages from the satellite."""
        from core.database import get_db_session
        from ai.device_node_service import device_node_service

        msg_type = message.get("type")
        
        if msg_type == "tool_result":
            request_id = message.get("request_id")
            if request_id in self.pending_requests:
                future = self.pending_requests[request_id]
                if not future.done():
                    future.set_result(message.get("result"))
        
        elif msg_type == "heartbeat":
            pass # Keep alive

        elif msg_type == "identify":
            # Register the device capabilities
            logger.info(f"Received identity for tenant {tenant_id}: {message}")
            try:
                with get_db_session() as db:
                # Map message to node_data structure
                node_data = {
                    "deviceId": message.get("metadata", {}).get("hostname", f"node-{tenant_id}"),
                    "name": message.get("metadata", {}).get("hostname", "Unknown Device"),
                    "type": "satellite_bridge",
                    "capabilities": message.get("capabilities", []),
                    "metadata": message.get("metadata", {})
                }
                device_node_service.register_node(db, tenant_id, node_data)
                db.close()
            except Exception as e:
                logger.error(f"Failed to register node identity: {e}")

satellite_service = SatelliteService()
