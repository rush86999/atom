"""
ATOM Unified Communication API
Updated with Mock/Real service toggle capability
"""

import os
import json
import time
from datetime import datetime
from typing import Dict, Any, Optional, List
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from loguru import logger

# Import unified implementation manager
from .unified_implementation import implementation_manager

app = FastAPI(
    title="ATOM Unified Communication API",
    description="Unified API for Slack and Microsoft Teams with Mock/Real service toggle",
    version="2.0.0"
)

# Request Models
class MessageRequest(BaseModel):
    content: str
    channel_id: str
    team_id: Optional[str] = None

class InstallRequest(BaseModel):
    user_id: str
    environment: Optional[str] = "mock"

class ImplementationSwitchRequest(BaseModel):
    service_name: str
    implementation_type: str

# Response Models
class HealthResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, Any]
    environment: str

class ImplementationStatusResponse(BaseModel):
    status: str
    timestamp: str
    services: Dict[str, Any]

# Utility Functions
def get_service(service_name: str):
    """Get currently active implementation for a service"""
    service = implementation_manager.get_service(service_name)
    if not service:
        raise HTTPException(
            status_code=503,
            detail=f"Service {service_name} not available"
        )
    return service

def format_response(ok: bool, data: Any = None, error: str = None) -> Dict[str, Any]:
    """Standardize API response format"""
    response = {
        "ok": ok,
        "timestamp": datetime.utcnow().isoformat()
    }
    
    if ok and data is not None:
        response.update(data)
    elif not ok and error:
        response["error"] = error
    
    return response

# Health and Status Endpoints
@app.get("/health", response_model=HealthResponse)
async def health_check():
    """Comprehensive health check"""
    try:
        # Get implementation status
        impl_status = implementation_manager.get_implementation_status()
        
        # Validate implementations
        validation = implementation_manager.validate_implementations()
        
        # Check individual service health
        services_health = {}
        for service_name in ['Slack', 'MicrosoftTeams']:
            try:
                service = get_service(service_name)
                if hasattr(service, 'health_check'):
                    health = await service.health_check()
                    services_health[service_name] = health
                else:
                    services_health[service_name] = {"status": "unknown"}
            except Exception as e:
                services_health[service_name] = {"status": "error", "error": str(e)}
        
        overall_status = "healthy"
        if not validation["valid"]:
            overall_status = "unhealthy"
        else:
            for service_health in services_health.values():
                if service_health.get("status") not in ["healthy", "unknown"]:
                    overall_status = "unhealthy"
                    break
        
        return HealthResponse(
            status=overall_status,
            timestamp=datetime.utcnow().isoformat(),
            services=services_health,
            environment=impl_status["environment"]
        )
        
    except Exception as e:
        logger.error(f"Health check error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Health check failed: {str(e)}"),
            status_code=500
        )

@app.get("/implementations", response_model=ImplementationStatusResponse)
async def get_implementations():
    """Get current implementation status"""
    try:
        status = implementation_manager.get_implementation_status()
        
        return ImplementationStatusResponse(
            status="success",
            timestamp=status["timestamp"],
            services=status["services"]
        )
        
    except Exception as e:
        logger.error(f"Get implementations error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get implementations: {str(e)}"),
            status_code=500
        )

@app.post("/implementations/switch")
async def switch_implementation(request: ImplementationSwitchRequest):
    """Switch implementation for a specific service"""
    try:
        success = implementation_manager.switch_implementation(
            request.service_name,
            request.implementation_type
        )
        
        if success:
            return format_response(
                True,
                {
                    "message": f"Switched {request.service_name} to {request.implementation_type}",
                    "service_name": request.service_name,
                    "old_implementation": implementation_manager.service_registry[request.service_name]['current'],
                    "new_implementation": request.implementation_type
                }
            )
        else:
            return JSONResponse(
                content=format_response(False, error="Failed to switch implementation"),
                status_code=400
            )
            
    except Exception as e:
        logger.error(f"Switch implementation error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Switch failed: {str(e)}"),
            status_code=500
        )

# Slack Endpoints
@app.post("/slack/install")
async def install_slack(request: InstallRequest):
    """Install Slack app for user"""
    try:
        slack_service = get_service('Slack')
        
        if request.environment == "real":
            result = await slack_service.install_with_user_id(request.user_id)
        else:
            # Mock implementation always succeeds
            result = format_response(True, {
                "ok": True,
                "install_url": "https://slack-mock-install-url.example.com",
                "state": "mock_state",
                "user_id": request.user_id,
                "environment": "mock"
            })
        
        return result
        
    except Exception as e:
        logger.error(f"Slack install error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Slack install failed: {str(e)}"),
            status_code=500
        )

@app.get("/slack/workspaces/{user_id}")
async def get_slack_workspaces(user_id: str):
    """Get user's Slack workspaces"""
    try:
        slack_service = get_service('Slack')
        result = await slack_service.get_workspaces(user_id)
        return result
        
    except Exception as e:
        logger.error(f"Slack workspaces error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get workspaces: {str(e)}"),
            status_code=500
        )

@app.get("/slack/channels/{team_id}/{user_id}")
async def get_slack_channels(team_id: str, user_id: str):
    """Get Slack channels for a workspace"""
    try:
        slack_service = get_service('Slack')
        result = await slack_service.get_channels(team_id, user_id)
        return result
        
    except Exception as e:
        logger.error(f"Slack channels error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get channels: {str(e)}"),
            status_code=500
        )

@app.get("/slack/messages/{channel_id}/{team_id}")
async def get_slack_messages(channel_id: str, team_id: str, limit: int = 50):
    """Get Slack messages from a channel"""
    try:
        slack_service = get_service('Slack')
        result = await slack_service.get_messages(channel_id, team_id, limit)
        return result
        
    except Exception as e:
        logger.error(f"Slack messages error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get messages: {str(e)}"),
            status_code=500
        )

@app.post("/slack/messages/send")
async def send_slack_message(request: MessageRequest):
    """Send message to Slack channel"""
    try:
        slack_service = get_service('Slack')
        result = await slack_service.send_message(
            request.channel_id,
            request.content,
            request.team_id
        )
        return result
        
    except Exception as e:
        logger.error(f"Slack send message error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to send message: {str(e)}"),
            status_code=500
        )

# Teams Endpoints
@app.get("/teams")
async def get_teams():
    """Get user's Teams"""
    try:
        teams_service = get_service('MicrosoftTeams')
        result = await teams_service.get_teams()
        return result
        
    except Exception as e:
        logger.error(f"Teams error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get teams: {str(e)}"),
            status_code=500
        )

@app.get("/teams/channels/{team_id}")
async def get_teams_channels(team_id: str):
    """Get Teams channels for a specific team"""
    try:
        teams_service = get_service('MicrosoftTeams')
        result = await teams_service.get_channels(team_id)
        return result
        
    except Exception as e:
        logger.error(f"Teams channels error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get channels: {str(e)}"),
            status_code=500
        )

@app.get("/teams/messages/{channel_id}/{team_id}")
async def get_teams_messages(channel_id: str, team_id: str, limit: int = 50):
    """Get Teams messages from a channel"""
    try:
        teams_service = get_service('MicrosoftTeams')
        result = await teams_service.get_messages(channel_id, team_id, limit)
        return result
        
    except Exception as e:
        logger.error(f"Teams messages error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get messages: {str(e)}"),
            status_code=500
        )

@app.post("/teams/messages/send")
async def send_teams_message(request: MessageRequest):
    """Send message to Teams channel"""
    try:
        teams_service = get_service('MicrosoftTeams')
        result = await teams_service.send_message(
            request.channel_id,
            request.content,
            request.team_id
        )
        return result
        
    except Exception as e:
        logger.error(f"Teams send message error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to send message: {str(e)}"),
            status_code=500
        )

# Unified Endpoints
@app.get("/workspaces")
async def get_all_workspaces(user_id: str):
    """Get workspaces from all services"""
    try:
        workspaces = {}
        
        # Get Slack workspaces
        try:
            slack_service = get_service('Slack')
            slack_result = await slack_service.get_workspaces(user_id)
            workspaces['slack'] = slack_result.get('workspaces', [])
        except Exception as e:
            logger.error(f"Failed to get Slack workspaces: {e}")
            workspaces['slack'] = []
        
        # Get Teams (team info similar to workspaces)
        try:
            teams_service = get_service('MicrosoftTeams')
            teams_result = await teams_service.get_teams()
            workspaces['teams'] = teams_result.get('teams', [])
        except Exception as e:
            logger.error(f"Failed to get Teams: {e}")
            workspaces['teams'] = []
        
        return format_response(
            True,
            {
                "workspaces": workspaces,
                "user_id": user_id,
                "services": list(workspaces.keys()),
                "total_count": sum(len(w) for w in workspaces.values())
            }
        )
        
    except Exception as e:
        logger.error(f"Get all workspaces error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get workspaces: {str(e)}"),
            status_code=500
        )

@app.get("/channels/{user_id}")
async def get_all_channels(user_id: str):
    """Get channels from all services for a user"""
    try:
        channels = {}
        
        # Get Slack channels
        slack_workspaces = []
        try:
            slack_service = get_service('Slack')
            slack_result = await slack_service.get_workspaces(user_id)
            slack_workspaces = slack_result.get('workspaces', [])
            
            slack_channels = []
            for workspace in slack_workspaces:
                workspace_channels = await slack_service.get_channels(workspace['id'], user_id)
                for channel in workspace_channels.get('channels', []):
                    channel['service'] = 'slack'
                    channel['workspace_name'] = workspace['name']
                    slack_channels.append(channel)
            
            channels['slack'] = slack_channels
            
        except Exception as e:
            logger.error(f"Failed to get Slack channels: {e}")
            channels['slack'] = []
        
        # Get Teams channels
        try:
            teams_service = get_service('MicrosoftTeams')
            teams_result = await teams_service.get_teams()
            
            teams_channels = []
            for team in teams_result.get('teams', []):
                team_channels = await teams_service.get_channels(team['id'])
                for channel in team_channels.get('channels', []):
                    channel['service'] = 'teams'
                    channel['team_name'] = team['name']
                    teams_channels.append(channel)
            
            channels['teams'] = teams_channels
            
        except Exception as e:
            logger.error(f"Failed to get Teams channels: {e}")
            channels['teams'] = []
        
        return format_response(
            True,
            {
                "channels": channels,
                "user_id": user_id,
                "services": list(channels.keys()),
                "total_count": sum(len(c) for c in channels.values())
            }
        )
        
    except Exception as e:
        logger.error(f"Get all channels error: {e}")
        return JSONResponse(
            content=format_response(False, error=f"Failed to get channels: {str(e)}"),
            status_code=500
        )

# Middleware for response logging
@app.middleware("http")
async def log_requests(request: Request, call_next):
    start_time = time.time()
    
    response = await call_next(request)
    
    process_time = time.time() - start_time
    
    logger.info(
        f"{request.method} {request.url.path} - "
        f"Status: {response.status_code} - "
        f"Time: {process_time:.3f}s"
    )
    
    return response

# Root endpoint
@app.get("/")
async def root():
    """API root with status"""
    impl_status = implementation_manager.get_implementation_status()
    
    return {
        "name": "ATOM Unified Communication API",
        "version": "2.0.0",
        "status": "running",
        "implementations": impl_status,
        "timestamp": datetime.utcnow().isoformat()
    }

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv('PORT', 8000))
    uvicorn.run(
        app, 
        host="0.0.0.0", 
        port=port,
        log_level="info"
    )