"""
ATOM Jira OAuth API Implementation
Complete OAuth flow for Jira integration
"""

import os
import json
import httpx
import hashlib
import base64
from typing import Dict, Any, Optional
from fastapi import FastAPI, HTTPException, Request, Response
from fastapi.responses import RedirectResponse
from pydantic import BaseModel
from cryptography.fernet import Fernet
from urllib.parse import urlencode, parse_qs

# Configuration
JIRA_CLIENT_ID = os.getenv("JIRA_CLIENT_ID", "")
JIRA_CLIENT_SECRET = os.getenv("JIRA_CLIENT_SECRET", "")
JIRA_REDIRECT_URI = os.getenv("JIRA_REDIRECT_URI", "http://localhost:8000/api/auth/jira/callback")
ENCRYPTION_KEY = os.getenv("ATOM_ENCRYPTION_KEY", Fernet.generate_key().decode())

# Initialize encryption
cipher_suite = Fernet(ENCRYPTION_KEY.encode())

# Storage (in production, use proper database)
token_storage: Dict[str, Dict[str, Any]] = {}

app = FastAPI(title="ATOM Jira OAuth API")

class OAuthStartRequest(BaseModel):
    user_id: str

class TokenStorage(BaseModel):
    user_id: str
    cloud_id: Optional[str] = None
    access_token: Optional[str] = None
    refresh_token: Optional[str] = None
    expires_at: Optional[float] = None

class JiraResourcesResponse(BaseModel):
    accessibleResources: list

def encrypt_data(data: str) -> str:
    """Encrypt sensitive data"""
    return cipher_suite.encrypt(data.encode()).decode()

def decrypt_data(encrypted_data: str) -> str:
    """Decrypt sensitive data"""
    return cipher_suite.decrypt(encrypted_data.encode()).decode()

def generate_state() -> str:
    """Generate random state parameter"""
    return hashlib.sha256(os.urandom(32)).hexdigest()[:16]

async def get_accessible_resources(access_token: str) -> list:
    """Get user's accessible Jira resources"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                "https://api.atlassian.com/oauth/token/accessible-resources",
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Error fetching accessible resources: {response.status_code}")
                return []
        except Exception as e:
            print(f"Exception fetching accessible resources: {e}")
            return []

async def discover_jira_projects(cloud_id: str, access_token: str) -> Dict[str, Any]:
    """Discover user's Jira projects and issues"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json"
    }
    
    discovery_data = {
        "projects": [],
        "issues": [],
        "total_count": 0,
        "discovered_at": None
    }
    
    try:
        async with httpx.AsyncClient() as client:
            # Get projects
            projects_url = f"https://{cloud_id}/rest/api/3/project/search"
            projects_response = await client.get(projects_url, headers=headers, timeout=30.0)
            
            if projects_response.status_code == 200:
                projects_data = projects_response.json()
                discovery_data["projects"] = projects_data.get("values", [])
                
                # Get recent issues (limited)
                issues_url = f"https://{cloud_id}/rest/api/3/search"
                issues_params = {
                    "jql": "status != 'Done' ORDER BY updated DESC",
                    "maxResults": 50,
                    "fields": "id,key,summary,status,assignee,priority,updated"
                }
                
                issues_response = await client.get(
                    issues_url, 
                    headers=headers, 
                    params=issues_params,
                    timeout=30.0
                )
                
                if issues_response.status_code == 200:
                    issues_data = issues_response.json()
                    discovery_data["issues"] = issues_data.get("issues", [])
                    discovery_data["total_count"] = issues_data.get("total", 0)
            
            discovery_data["discovered_at"] = "2025-06-17T00:00:00Z"
            
    except Exception as e:
        print(f"Error discovering Jira data: {e}")
    
    return discovery_data

@app.get("/")
async def root():
    return {"message": "ATOM Jira OAuth API", "status": "running"}

@app.get("/api/auth/jira/start")
async def start_oauth(request: Request, user_id: str):
    """
    Start Jira OAuth flow
    Returns Atlassian authorization URL
    """
    try:
        # Generate state parameter
        state = generate_state()
        
        # Store state temporarily
        token_storage[f"state_{state}"] = {
            "user_id": user_id,
            "created_at": httpx._utils.current_time()
        }
        
        # Build OAuth URL
        auth_params = {
            "audience": "api.atlassian.com",
            "client_id": JIRA_CLIENT_ID,
            "scope": "read:jira-work read:issue-details:jira read:comments:jira read:attachments:jira",
            "redirect_uri": JIRA_REDIRECT_URI,
            "response_type": "code",
            "state": state,
            "prompt": "consent"
        }
        
        auth_url = f"https://auth.atlassian.com/authorize?{urlencode(auth_params)}"
        
        return {
            "auth_url": auth_url,
            "state": state,
            "user_id": user_id,
            "expires_in": 600  # 10 minutes
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OAuth start failed: {str(e)}")

@app.get("/api/auth/jira/callback")
async def oauth_callback(
    request: Request,
    code: Optional[str] = None,
    state: Optional[str] = None,
    error: Optional[str] = None,
    error_description: Optional[str] = None
):
    """
    Handle Jira OAuth callback
    Exchange code for access token and discover resources
    """
    try:
        # Check for OAuth errors
        if error:
            return RedirectResponse(
                url=f"/oauth/error?error={error}&description={error_description or 'Unknown error'}"
            )
        
        if not code or not state:
            return RedirectResponse(
                url="/oauth/error?error=missing_params&description=Missing authorization code or state"
            )
        
        # Verify state
        state_key = f"state_{state}"
        if state_key not in token_storage:
            return RedirectResponse(
                url="/oauth/error?error=invalid_state&description=Invalid or expired state parameter"
            )
        
        stored_state = token_storage[state_key]
        user_id = stored_state["user_id"]
        
        # Clean up state
        del token_storage[state_key]
        
        # Exchange authorization code for access token
        token_data = await exchange_code_for_token(code)
        
        if not token_data:
            return RedirectResponse(
                url="/oauth/error?error=token_exchange_failed&description=Failed to exchange code for token"
            )
        
        # Get accessible resources
        resources = await get_accessible_resources(token_data["access_token"])
        
        if not resources:
            return RedirectResponse(
                url="/oauth/error?error=no_resources&description=No accessible Jira resources found"
            )
        
        # Store tokens for each resource
        for resource in resources:
            cloud_id = resource["id"]
            
            # Discover Jira projects and issues for this resource
            discovery_data = await discover_jira_projects(cloud_id, token_data["access_token"])
            
            # Encrypt and store tokens
            encrypted_access_token = encrypt_data(token_data["access_token"])
            encrypted_refresh_token = encrypt_data(token_data["refresh_token"]) if token_data.get("refresh_token") else None
            
            storage_key = f"{user_id}_{cloud_id}"
            token_storage[storage_key] = {
                "user_id": user_id,
                "cloud_id": cloud_id,
                "name": resource["name"],
                "url": resource["url"],
                "scopes": resource["scopes"],
                "access_token": encrypted_access_token,
                "refresh_token": encrypted_refresh_token,
                "token_type": token_data["token_type"],
                "expires_in": token_data["expires_in"],
                "created_at": httpx._utils.current_time(),
                "discovery": discovery_data
            }
        
        # Return success with stored resource info
        return RedirectResponse(
            url=f"/oauth/success?user_id={user_id}&resources={len(resources)}"
        )
        
    except Exception as e:
        print(f"OAuth callback error: {e}")
        return RedirectResponse(
            url=f"/oauth/error?error=callback_failed&description={str(e)}"
        )

@app.get("/api/auth/jira/resources")
async def get_user_resources(request: Request, user_id: str):
    """
    Get user's stored Jira resources and discovery data
    """
    try:
        user_resources = []
        
        # Find all resources for this user
        for key, data in token_storage.items():
            if key.startswith(f"{user_id}_") and key != f"{user_id}_state":
                # Decrypt sensitive data
                access_token = decrypt_data(data["access_token"])
                refresh_token = None
                if data["refresh_token"]:
                    refresh_token = decrypt_data(data["refresh_token"])
                
                resource_info = {
                    "cloud_id": data["cloud_id"],
                    "name": data["name"],
                    "url": data["url"],
                    "scopes": data["scopes"],
                    "token_type": data["token_type"],
                    "expires_in": data["expires_in"],
                    "discovery": data["discovery"],
                    "tokens": {
                        "access_token": access_token[:10] + "...",  # Partial for security
                        "has_refresh_token": bool(refresh_token),
                        "created_at": data["created_at"]
                    }
                }
                user_resources.append(resource_info)
        
        return {
            "user_id": user_id,
            "resources": user_resources,
            "total_resources": len(user_resources),
            "timestamp": httpx._utils.current_time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get resources: {str(e)}")

@app.get("/api/auth/jira/{cloud_id}/projects")
async def get_jira_projects(request: Request, user_id: str, cloud_id: str):
    """
    Get specific Jira projects for a cloud instance
    """
    try:
        storage_key = f"{user_id}_{cloud_id}"
        if storage_key not in token_storage:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        data = token_storage[storage_key]
        access_token = decrypt_data(data["access_token"])
        
        # Refresh token if needed
        if is_token_expired(data):
            token_data = await refresh_access_token(data["refresh_token"])
            if token_data:
                access_token = token_data["access_token"]
                data["access_token"] = encrypt_data(access_token)
                data["created_at"] = httpx._utils.current_time()
        
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Get projects
            projects_url = f"https://{cloud_id}/rest/api/3/project/search"
            response = await client.get(projects_url, headers=headers, timeout=30.0)
            
            if response.status_code == 200:
                projects_data = response.json()
                return {
                    "cloud_id": cloud_id,
                    "projects": projects_data.get("values", []),
                    "total": projects_data.get("total", 0),
                    "timestamp": httpx._utils.current_time()
                }
            else:
                raise HTTPException(status_code=response.status_code, detail="Failed to fetch projects")
                
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get projects: {str(e)}")

@app.delete("/api/auth/jira/{cloud_id}")
async def revoke_access(request: Request, user_id: str, cloud_id: str):
    """
    Revoke access to a specific Jira cloud instance
    """
    try:
        storage_key = f"{user_id}_{cloud_id}"
        if storage_key not in token_storage:
            raise HTTPException(status_code=404, detail="Resource not found")
        
        # Remove stored tokens
        del token_storage[storage_key]
        
        return {
            "message": "Access revoked successfully",
            "user_id": user_id,
            "cloud_id": cloud_id,
            "timestamp": httpx._utils.current_time()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to revoke access: {str(e)}")

async def exchange_code_for_token(code: str) -> Optional[Dict[str, Any]]:
    """Exchange authorization code for access token"""
    try:
        token_url = "https://auth.atlassian.com/oauth/token"
        
        data = {
            "grant_type": "authorization_code",
            "client_id": JIRA_CLIENT_ID,
            "client_secret": JIRA_CLIENT_SECRET,
            "code": code,
            "redirect_uri": JIRA_REDIRECT_URI
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=data, headers=headers, timeout=30.0)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Token exchange failed: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"Token exchange exception: {e}")
        return None

async def refresh_access_token(encrypted_refresh_token: str) -> Optional[Dict[str, Any]]:
    """Refresh access token using refresh token"""
    try:
        refresh_token = decrypt_data(encrypted_refresh_token)
        
        token_url = "https://auth.atlassian.com/oauth/token"
        
        data = {
            "grant_type": "refresh_token",
            "client_id": JIRA_CLIENT_ID,
            "client_secret": JIRA_CLIENT_SECRET,
            "refresh_token": refresh_token
        }
        
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(token_url, json=data, headers=headers, timeout=30.0)
            
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Token refresh failed: {response.status_code} - {response.text}")
                return None
                
    except Exception as e:
        print(f"Token refresh exception: {e}")
        return None

def is_token_expired(token_data: Dict[str, Any]) -> bool:
    """Check if token is expired or close to expiry"""
    try:
        created_at = token_data.get("created_at", 0)
        expires_in = token_data.get("expires_in", 3600)  # Default 1 hour
        
        # Consider expired if within 5 minutes of expiry
        current_time = httpx._utils.current_time()
        expiry_time = created_at + expires_in - 300  # 5 minute buffer
        
        return current_time >= expiry_time
        
    except Exception:
        return True  # Assume expired if we can't check

# Health check endpoint
@app.get("/api/auth/jira/health")
async def health_check():
    """Check OAuth service health"""
    try:
        # Check configuration
        config_ok = all([JIRA_CLIENT_ID, JIRA_CLIENT_SECRET, JIRA_REDIRECT_URI])
        
        # Test Atlassian connectivity
        async with httpx.AsyncClient() as client:
            response = await client.get("https://auth.atlassian.com", timeout=10.0)
            atlassian_reachable = response.status_code == 200
        
        return {
            "status": "healthy" if config_ok and atlassian_reachable else "unhealthy",
            "config_ok": config_ok,
            "atlassian_reachable": atlassian_reachable,
            "timestamp": httpx._utils.current_time()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": httpx._utils.current_time()
        }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)