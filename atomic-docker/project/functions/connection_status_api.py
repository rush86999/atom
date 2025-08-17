"""
Connection Status API

API endpoints for checking the connection/tokens status of integrated services.
This replaces the mock status checks in the frontend.
"""

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
import os
import json
from datetime import datetime, timedelta
import redis
from typing import Dict, Optional, Any
import logging

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Atom Connection Status API", version="1.0.0")

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Redis configuration
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
try:
    redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    redis_client.ping()
    logger.info(f"Connected to Redis at {REDIS_URL}")
except Exception as e:
    logger.warning(f"Redis connection failed: {e}")
    redis_client = None

# Service status storage key
STATUS_KEY = "atom:connection_status"

def dict_to_redis(data: Dict[str, Any]) -> Dict[str, str]:
    """Convert dict to string values for Redis storage"""
    return {k: json.dumps(v) if isinstance(v, (dict, list)) else str(v) for k, v in data.items()}

def redis_to_dict(data: Dict[str, str]) -> Dict[str, Any]:
    """Convert Redis string values back to appropriate Python types"""
    result = {}
    for k, v in data.items():
        try:
            result[k] = json.loads(v)
        except (json.JSONDecodeError, ValueError):
            result[k] = v
    return result

def check_google_credentials(user_id: str) -> Dict[str, Any]:
    """Check Google Calendar/Drive connection status"""
    key = f"google_credentials:{user_id}"
    if redis_client and redis_client.exists(key):
        credentials = redis_client.hgetall(key)
        return {
            "connected": True,
            "email": credentials.get("email", "Unknown"),
            "last_updated": credentials.get("updated_at", datetime.now().isoformat()),
            "scopes": json.loads(credentials.get("scopes", "[]"))
        }
    return {"connected": False, "message": "No Google credentials found"}

def check_slack_credentials(user_id: str) -> Dict[str, Any]:
    """Check Slack connection status"""
    key = f"slack_oauth:{user_id}:access_token"
    if redis_client and redis_client.exists(key):
        team_info = redis_client.hgetall(f"slack_oauth:{user_id}:team_info")
        return {
            "connected": True,
            "team_name": team_info.get("team_name", "Unknown"),
            "user_name": team_info.get("user_name", "Unknown"),
            "last_updated": team_info.get("updated_at", datetime.now().isoformat())
        }
    return {"connected": False, "message": "No Slack OAuth found"}

def check_microsoft_credentials(user_id: str) -> Dict[str, Any]:
    """Check Microsoft Teams/Outlook connection status"""
    key = f"microsoft_oauth:{user_id}:access_token"
    if redis_client and redis_client.exists(key):
        team_info = redis_client.hgetall(f"microsoft_oauth:{user_id}:user_info")
        return {
            "connected": True,
            "email": team_info.get("email", "Unknown"),
            "display_name": team_info.get("display_name", "Unknown"),
            "last_updated": team_info.get("updated_at", datetime.now().isoformat())
        }
    return {"connected": False, "message": "No Microsoft OAuth found"}

def check_linkedin_credentials(user_id: str) -> Dict[str, Any]:
    """Check LinkedIn connection status"""
    key = f"linkedin_oauth:{user_id}:access_token"
    if redis_client and redis_client.exists(key):
        profile = redis_client.hgetall(f"linkedin_oauth:{user_id}:profile")
        return {
            "connected": True,
            "name": profile.get("localizedFirstName", "") + " " + profile.get("localizedLastName", ""),
            "headline": profile.get("headline", ""),
            "last_updated": profile.get("updated_at", datetime.now().isoformat())
        }
    return {"connected": False, "message": "No LinkedIn OAuth found"}

def check_twitter_credentials(user_id: str) -> Dict[str, Any]:
"""Check Twitter connection status"""
key = f"twitter_oauth:{user_id}:access_token"
if redis_client and redis_client.exists(key):
    profile = redis_client.hgetall(f"twitter_oauth:{user_id}:profile")
    return {
        "connected": True,
        "username": profile.get("username", ""),
        "name": profile.get("name", ""),
        "last_updated": profile.get("updated_at", datetime.now().isoformat())
    }
return {"connected": False, "message": "No Twitter OAuth found"}

def check_plaid_credentials(user_id: str) -> Dict[str, Any]:
"""Check Plaid/banking connection status"""
key = f"plaid_access_token:{user_id}"
if redis_client and redis_client.exists(key):
    return {
        "connected": True,
        "institution_count": int(redis_client.get(f"plaid_institution_count:{user_id}") or "0"),
        "last_updated": redis_client.get(f"plaid_last_updated:{user_id}") or datetime.now().isoformat()
    }
return {"connected": False, "message": "No banking connections found"}

@app.get("/")
async def health_check():
"""Health check endpoint"""
return {"status": "healthy", "service": "atom-connection-status"}

@app.get("/status/{user_id}")
async def get_all_connections(user_id: str):
"""Get status of all user connections"""
try:
    return {
        "user_id": user_id,
        "timestamp": datetime.now().isoformat(),
        "connections": {
            "google": check_google_credentials(user_id),
            "slack": check_slack_credentials(user_id),
            "microsoft": check_microsoft_credentials(user_id),
            "linkedin": check_linkedin_credentials(user_id),
            "twitter": check_twitter_credentials(user_id),
            "plaid": check_plaid_credentials(user_id)
        }
    }
except Exception as e:
    logger.error(f"Error checking connections for user {user_id}: {e}")
    raise HTTPException(status_code=500, detail=str(e))

@app.get("/status/{user_id}/{service}")
async def get_service_connection(user_id: str, service: str):
"""Get status of a specific service"""
service_checkers = {
    "google": check_google_credentials,
    "slack": check_slack_credentials,
    "microsoft": check_microsoft_credentials,
    "linkedin": check_linkedin_credentials,
    "twitter": check_twitter_credentials,
    "plaid": check_plaid_credentials
}

if service not in service_checkers:
    raise HTTPException(status_code=404, detail="Service not found")

try:
    return {
        "user_id": user_id,
        "service": service,
        "status": service_checkers[service](user_id),
        "timestamp": datetime.now().isoformat()
    }
except Exception as e:
    logger.error(f"Error checking {service} for user {user_id}: {e}")
    raise HTTPException(status_code=500, detail=str(e))

@app.post("/status/{user_id}/{service}")
async def update_service_status(user_id: str, service: str, status: dict):
"""Manually update a service status (for testing)"""
if not redis_client:
    raise HTTPException(status_code=503, detail="Redis not available")

key = f"manual_status:{user_id}:{service}"
redis_client.hmset(key, dict_to_redis({**status, "updated_at": datetime.now().isoformat()}))

return {"message": f"Status updated for {service}", "status": status}

if __name__ == "__main__":
import uvicorn
uvicorn.run(app, host="0.0.0.0", port=8005)
