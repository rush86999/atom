from fastapi import FastAPI, HTTPException, Depends
from pydantic import BaseModel
import uvicorn
import os
import logging
import datetime
from typing import Optional, List, Dict, Any
import aiohttp
import aiofiles
from dropbox import Dropbox
from dropbox.exceptions import AuthError, ApiError
import asyncio

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Dropbox Service API",
    description="API for Dropbox integration and file operations",
    version="1.0.0"
)

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    dropbox_connected: bool = False

class DropboxAuthRequest(BaseModel):
    auth_code: str
    redirect_uri: str

class DropboxFile(BaseModel):
    id: str
    name: str
    path: str
    size: int
    modified: str
    is_folder: bool

class DropboxFileUpload(BaseModel):
    content: str  # Base64 encoded file content
    path: str
    filename: str

class DropboxFileDownload(BaseModel):
    path: str
    content: Optional[str] = None  # Base64 encoded content for response

# Configuration (would come from environment variables in production)
DROPBOX_APP_KEY = os.getenv("DROPBOX_APP_KEY", "your_dropbox_app_key")
DROPBOX_APP_SECRET = os.getenv("DROPBOX_APP_SECRET", "your_dropbox_app_secret")
DROPBOX_ACCESS_TOKEN = os.getenv("DROPBOX_ACCESS_TOKEN", "")

# Global Dropbox client (would be managed per user in production)
dropbox_client = None

async def get_dropbox_client():
    """Get or create Dropbox client"""
    global dropbox_client
    if dropbox_client is None and DROPBOX_ACCESS_TOKEN:
        try:
            dropbox_client = Dropbox(DROPBOX_ACCESS_TOKEN)
            # Verify the token is valid
            dropbox_client.users_get_current_account()
            logger.info("Dropbox client initialized successfully")
        except (AuthError, ApiError) as e:
            logger.error(f"Failed to initialize Dropbox client: {e}")
            dropbox_client = None
    return dropbox_client

@app.get("/")
async def root():
    return {"message": "Dropbox Service API", "version": "1.0.0"}

@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    client = await get_dropbox_client()
    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.datetime.now().isoformat(),
        dropbox_connected=client is not None
    )

@app.get("/auth/url")
async def get_auth_url():
    """Get Dropbox OAuth2 authorization URL"""
    try:
        from dropbox.oauth import DropboxOAuth2Flow
        auth_flow = DropboxOAuth2Flow(
            DROPBOX_APP_KEY,
            DROPBOX_APP_SECRET,
            redirect_uri="http://localhost:5001/auth/callback",
            session={},
            csrf_token_session_key="dropbox_csrf_token"
        )
        auth_url = auth_flow.start()
        return {"auth_url": auth_url}
    except Exception as e:
        logger.error(f"Error generating auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/auth/token")
async def exchange_auth_code(request: DropboxAuthRequest):
    """Exchange authorization code for access token"""
    try:
        from dropbox.oauth import DropboxOAuth2Flow
        auth_flow = DropboxOAuth2Flow(
            DROPBOX_APP_KEY,
            DROPBOX_APP_SECRET,
            redirect_uri=request.redirect_uri,
            session={},
            csrf_token_session_key="dropbox_csrf_token"
        )
        result = auth_flow.finish(request.auth_code)
        return {
            "access_token": result.access_token,
            "account_id": result.account_id,
            "user_id": result.user_id
        }
    except Exception as e:
        logger.error(f"Error exchanging auth code: {e}")
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/files/list")
async def list_files(path: str = ""):
    """List files and folders in Dropbox"""
    client = await get_dropbox_client()
    if not client:
        raise HTTPException(status_code=401, detail="Dropbox not authenticated")

    try:
        if path == "":
            result = client.files_list_folder("")
        else:
            result = client.files_list_folder(path)

        files = []
        for entry in result.entries:
            files.append(DropboxFile(
                id=entry.id,
                name=entry.name,
                path=entry.path_display,
                size=getattr(entry, 'size', 0),
                modified=entry.server_modified.isoformat() if hasattr(entry, 'server_modified') else "",
                is_folder=isinstance(entry, dropbox.files.FolderMetadata)
            ))

        return {"files": files, "has_more": result.has_more}

    except ApiError as e:
        logger.error(f"Dropbox API error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error listing files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/files/download/{path:path}")
async def download_file(path: str):
    """Download a file from Dropbox"""
    client = await get_dropbox_client()
    if not client:
        raise HTTPException(status_code=401, detail="Dropbox not authenticated")

    try:
        metadata, response = client.files_download(path)
        content = response.content

        return DropboxFileDownload(
            path=path,
            content=content.decode('utf-8') if isinstance(content, bytes) else content
        )

    except ApiError as e:
        logger.error(f"Dropbox API error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error downloading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/files/upload")
async def upload_file(upload: DropboxFileUpload):
    """Upload a file to Dropbox"""
    client = await get_dropbox_client()
    if not client:
        raise HTTPException(status_code=401, detail="Dropbox not authenticated")

    try:
        # Ensure the path ends with the filename
        full_path = f"{upload.path.rstrip('/')}/{upload.filename}"

        # Upload the file
        client.files_upload(
            upload.content.encode('utf-8'),
            full_path,
            mode=dropbox.files.WriteMode.overwrite
        )

        return {"status": "success", "path": full_path}

    except ApiError as e:
        logger.error(f"Dropbox API error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/files/delete/{path:path}")
async def delete_file(path: str):
    """Delete a file from Dropbox"""
    client = await get_dropbox_client()
    if not client:
        raise HTTPException(status_code=401, detail="Dropbox not authenticated")

    try:
        client.files_delete_v2(path)
        return {"status": "success", "message": f"File {path} deleted"}

    except ApiError as e:
        logger.error(f"Dropbox API error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error deleting file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/account/info")
async def get_account_info():
    """Get current Dropbox account information"""
    client = await get_dropbox_client()
    if not client:
        raise HTTPException(status_code=401, detail="Dropbox not authenticated")

    try:
        account = client.users_get_current_account()
        return {
            "account_id": account.account_id,
            "email": account.email,
            "name": account.name.display_name,
            "country": account.country,
            "locale": account.locale
        }

    except ApiError as e:
        logger.error(f"Dropbox API error: {e}")
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Error getting account info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5001)
