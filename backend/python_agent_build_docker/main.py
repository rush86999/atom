import asyncio
import datetime
import json
import logging
import os
from typing import Any, Dict, List, Optional
import aiohttp
import deepgram
import uvicorn
from fastapi import FastAPI, HTTPException
from notion_client import AsyncClient as NotionClient
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Python Agent API",
    description="API for Python agent services including Notion, Deepgram, and other integrations",
    version="1.0.0"
)

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str
    services: Dict[str, bool]

class NotionPageRequest(BaseModel):
    database_id: str
    filter: Optional[Dict[str, Any]] = None
    sorts: Optional[List[Dict[str, Any]]] = None

class NotionPageCreate(BaseModel):
    database_id: str
    properties: Dict[str, Any]
    content: Optional[str] = None

class TranscriptionRequest(BaseModel):
    audio_url: Optional[str] = None
    audio_data: Optional[str] = None  # Base64 encoded
    language: str = "en"
    model: str = "nova-2"

class TranscriptionResponse(BaseModel):
    transcript: str
    confidence: float
    words: List[Dict[str, Any]]
    duration: float

# Initialize clients
notion_client = None
deepgram_client = None

async def get_notion_client():
    """Get or initialize Notion client"""
    global notion_client
    if notion_client is None:
        notion_token = os.getenv("NOTION_API_TOKEN")
        if notion_token:
            notion_client = NotionClient(auth=notion_token)
            logger.info("Notion client initialized")
        else:
            logger.warning("NOTION_API_TOKEN not set, Notion integration disabled")
    return notion_client

async def get_deepgram_client():
    """Get or initialize Deepgram client"""
    global deepgram_client
    if deepgram_client is None:
        deepgram_key = os.getenv("DEEPGRAM_API_KEY")
        if deepgram_key:
            deepgram_client = deepgram.Deepgram(deepgram_key)
            logger.info("Deepgram client initialized")
        else:
            logger.warning("DEEPGRAM_API_KEY not set, Deepgram integration disabled")
    return deepgram_client

@app.get("/")
async def root():
    return {"message": "Python Agent API", "version": "1.0.0"}

@app.get("/healthz", response_model=HealthResponse)
async def health_check():
    notion_status = await get_notion_client() is not None
    deepgram_status = await get_deepgram_client() is not None

    return HealthResponse(
        status="ok",
        version="1.0.0",
        timestamp=datetime.datetime.now().isoformat(),
        services={
            "notion": notion_status,
            "deepgram": deepgram_status,
            "database": True  # Always assume database is available
        }
    )

@app.get("/notion/databases")
async def list_notion_databases():
    """List all Notion databases accessible to the integration"""
    client = await get_notion_client()
    if not client:
        raise HTTPException(status_code=501, detail="Notion integration not configured")

    try:
        response = await client.search(filter={"property": "object", "value": "database"})
        return {"databases": response.get("results", [])}
    except Exception as e:
        logger.error(f"Error listing Notion databases: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/notion/pages/query")
async def query_notion_pages(request: NotionPageRequest):
    """Query pages from a Notion database"""
    client = await get_notion_client()
    if not client:
        raise HTTPException(status_code=501, detail="Notion integration not configured")

    try:
        response = await client.databases.query(
            database_id=request.database_id,
            filter=request.filter,
            sorts=request.sorts
        )
        return {"pages": response.get("results", [])}
    except Exception as e:
        logger.error(f"Error querying Notion pages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/notion/pages")
async def create_notion_page(request: NotionPageCreate):
    """Create a new page in a Notion database"""
    client = await get_notion_client()
    if not client:
        raise HTTPException(status_code=501, detail="Notion integration not configured")

    try:
        page_data = {
            "parent": {"database_id": request.database_id},
            "properties": request.properties
        }

        if request.content:
            page_data["children"] = [
                {
                    "object": "block",
                    "type": "paragraph",
                    "paragraph": {
                        "rich_text": [{"type": "text", "text": {"content": request.content}}]
                    }
                }
            ]

        response = await client.pages.create(**page_data)
        return {"page": response}
    except Exception as e:
        logger.error(f"Error creating Notion page: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/transcribe")
async def transcribe_audio(request: TranscriptionRequest):
    """Transcribe audio using Deepgram"""
    client = await get_deepgram_client()
    if not client:
        raise HTTPException(status_code=501, detail="Deepgram integration not configured")

    try:
        source = {}
        if request.audio_url:
            source = {"url": request.audio_url}
        elif request.audio_data:
            # For base64 audio data, we'd need to handle it differently
            raise HTTPException(status_code=400, detail="Base64 audio not yet implemented")
        else:
            raise HTTPException(status_code=400, detail="Either audio_url or audio_data must be provided")

        response = await client.transcription.prerecorded(
            source,
            {
                "smart_format": True,
                "model": request.model,
                "language": request.language,
                "punctuate": True
            }
        )

        transcript = response["results"]["channels"][0]["alternatives"][0]
        return TranscriptionResponse(
            transcript=transcript["transcript"],
            confidence=transcript["confidence"],
            words=transcript.get("words", []),
            duration=response["metadata"]["duration"]
        )
    except Exception as e:
        logger.error(f"Error transcribing audio: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/research/projects")
async def get_research_projects():
    """Get research projects from Notion"""
    database_id = os.getenv("NOTION_RESEARCH_PROJECTS_DB_ID")
    if not database_id:
        raise HTTPException(status_code=501, detail="Research projects database not configured")

    return await query_notion_pages(NotionPageRequest(database_id=database_id))

@app.get("/research/tasks")
async def get_research_tasks():
    """Get research tasks from Notion"""
    database_id = os.getenv("NOTION_RESEARCH_TASKS_DB_ID")
    if not database_id:
        raise HTTPException(status_code=501, detail="Research tasks database not configured")

    return await query_notion_pages(NotionPageRequest(database_id=database_id))

@app.get("/notes")
async def get_notes():
    """Get notes from Notion"""
    database_id = os.getenv("NOTION_NOTES_DATABASE_ID")
    if not database_id:
        raise HTTPException(status_code=501, detail="Notes database not configured")

    return await query_notion_pages(NotionPageRequest(database_id=database_id))

@app.post("/ai/process")
async def process_with_ai(prompt: str, context: Optional[Dict[str, Any]] = None):
    """Process data with AI models"""
    # Placeholder implementation - would integrate with various AI services
    try:
        # Simulate AI processing
        await asyncio.sleep(0.1)

        return {
            "result": f"Processed: {prompt}",
            "context": context or {},
            "confidence": 0.85
        }
    except Exception as e:
        logger.error(f"Error processing with AI: {e}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=5000)
