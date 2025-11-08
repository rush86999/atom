from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional
import logging
import asyncio
from google_docs_service import GoogleDocsService
from google_sheets_service import GoogleSheetsService
from google_slides_service import GoogleSlidesService
from google_keep_service import GoogleKeepService
from google_tasks_service import GoogleTasksService

router = APIRouter(prefix="/api/google-workspace", tags=["google-workspace"])
logger = logging.getLogger(__name__)

# Service cache
google_service_cache = {}

async def get_google_docs_service(request: Request) -> GoogleDocsService:
    """Get Google Docs service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"google_docs_{user_id}"
        if cache_key not in google_service_cache:
            google_service_cache[cache_key] = GoogleDocsService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            await google_service_cache[cache_key].initialize(db_pool)
        
        return google_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Google Docs service: {e}")
        raise HTTPException(status_code=500, detail="Google Docs service initialization failed")

async def get_google_sheets_service(request: Request) -> GoogleSheetsService:
    """Get Google Sheets service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"google_sheets_{user_id}"
        if cache_key not in google_service_cache:
            google_service_cache[cache_key] = GoogleSheetsService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            await google_service_cache[cache_key].initialize(db_pool)
        
        return google_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Google Sheets service: {e}")
        raise HTTPException(status_code=500, detail="Google Sheets service initialization failed")

async def get_google_slides_service(request: Request) -> GoogleSlidesService:
    """Get Google Slides service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"google_slides_{user_id}"
        if cache_key not in google_service_cache:
            google_service_cache[cache_key] = GoogleSlidesService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            await google_service_cache[cache_key].initialize(db_pool)
        
        return google_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Google Slides service: {e}")
        raise HTTPException(status_code=500, detail="Google Slides service initialization failed")

async def get_google_keep_service(request: Request) -> GoogleKeepService:
    """Get Google Keep service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"google_keep_{user_id}"
        if cache_key not in google_service_cache:
            google_service_cache[cache_key] = GoogleKeepService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            await google_service_cache[cache_key].initialize(db_pool)
        
        return google_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Google Keep service: {e}")
        raise HTTPException(status_code=500, detail="Google Keep service initialization failed")

async def get_google_tasks_service(request: Request) -> GoogleTasksService:
    """Get Google Tasks service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"google_tasks_{user_id}"
        if cache_key not in google_service_cache:
            google_service_cache[cache_key] = GoogleTasksService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            await google_service_cache[cache_key].initialize(db_pool)
        
        return google_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Google Tasks service: {e}")
        raise HTTPException(status_code=500, detail="Google Tasks service initialization failed")

@router.get("/health")
async def health_check():
    """Health check for Google Workspace integration"""
    try:
        # Check environment variables
        required_vars = ["GOOGLE_CLIENT_ID", "GOOGLE_CLIENT_SECRET"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }
        
        services = {
            "google_docs": "available",
            "google_sheets": "available",
            "google_slides": "available",
            "google_keep": "available",
            "google_tasks": "available"
        }
        
        return {
            "status": "healthy",
            "service": "google-workspace",
            "services": services,
            "timestamp": "2025-11-07T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Google Workspace health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

# Google Docs endpoints
@router.post("/docs")
async def get_google_docs(
    request: Request,
    docs_service: GoogleDocsService = Depends(get_google_docs_service)
):
    """Get Google Docs documents"""
    try:
        data = await request.json()
        query = data.get("query")
        page_size = data.get("page_size", 50)
        
        result = await docs_service.get_documents(query, page_size)
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Google Docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/docs/create")
async def create_google_doc(
    doc_data: Dict[str, Any],
    request: Request,
    docs_service: GoogleDocsService = Depends(get_google_docs_service)
):
    """Create a new Google Doc"""
    try:
        title = doc_data.get("title")
        content = doc_data.get("content")
        folder_id = doc_data.get("folder_id")
        
        result = await docs_service.create_document(title, content, folder_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create Google Doc: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/docs/{document_id}/content")
async def get_doc_content(
    document_id: str,
    request: Request,
    docs_service: GoogleDocsService = Depends(get_google_docs_service)
):
    """Get Google Doc content"""
    try:
        result = await docs_service.get_document_content(document_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get doc content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/docs/{document_id}/content/update")
async def update_doc_content(
    document_id: str,
    content_data: Dict[str, Any],
    request: Request,
    docs_service: GoogleDocsService = Depends(get_google_docs_service)
):
    """Update Google Doc content"""
    try:
        content = content_data.get("content")
        
        result = await docs_service.update_document_content(document_id, content)
        return result
        
    except Exception as e:
        logger.error(f"Failed to update doc content: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/docs/search")
async def search_google_docs(
    search_data: Dict[str, Any],
    request: Request,
    docs_service: GoogleDocsService = Depends(get_google_docs_service)
):
    """Search Google Docs"""
    try:
        query = search_data.get("query")
        search_scope = search_data.get("scope", "all")
        
        result = await docs_service.search_documents(query, search_scope)
        return result
        
    except Exception as e:
        logger.error(f"Failed to search Google Docs: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Google Sheets endpoints
@router.post("/sheets")
async def get_google_sheets(
    request: Request,
    sheets_service: GoogleSheetsService = Depends(get_google_sheets_service)
):
    """Get Google Sheets spreadsheets"""
    try:
        data = await request.json()
        query = data.get("query")
        page_size = data.get("page_size", 50)
        
        result = await sheets_service.get_spreadsheets(query, page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Google Sheets: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sheets/create")
async def create_google_sheet(
    sheet_data: Dict[str, Any],
    request: Request,
    sheets_service: GoogleSheetsService = Depends(get_google_sheets_service)
):
    """Create a new Google Sheet"""
    try:
        title = sheet_data.get("title")
        sheets_data = sheet_data.get("sheets", [])
        folder_id = sheet_data.get("folder_id")
        
        result = await sheets_service.create_spreadsheet(title, sheets_data, folder_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create Google Sheet: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sheets/{spreadsheet_id}/data")
async def get_sheet_data(
    spreadsheet_id: str,
    request: Request,
    sheets_service: GoogleSheetsService = Depends(get_google_sheets_service)
):
    """Get Google Sheet data"""
    try:
        data = await request.json()
        sheet_name = data.get("sheet_name")
        range_str = data.get("range", "A1:Z1000")
        
        result = await sheets_service.get_sheet_data(spreadsheet_id, sheet_name, range_str)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get sheet data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/sheets/{spreadsheet_id}/data/update")
async def update_sheet_data(
    spreadsheet_id: str,
    data_request: Dict[str, Any],
    request: Request,
    sheets_service: GoogleSheetsService = Depends(get_google_sheets_service)
):
    """Update Google Sheet data"""
    try:
        sheet_name = data_request.get("sheet_name")
        data = data_request.get("data")
        range_str = data_request.get("range")
        
        result = await sheets_service.update_sheet_data(spreadsheet_id, sheet_name, data, range_str)
        return result
        
    except Exception as e:
        logger.error(f"Failed to update sheet data: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Google Slides endpoints
@router.post("/slides")
async def get_google_slides(
    request: Request,
    slides_service: GoogleSlidesService = Depends(get_google_slides_service)
):
    """Get Google Slides presentations"""
    try:
        data = await request.json()
        query = data.get("query")
        page_size = data.get("page_size", 50)
        
        result = await slides_service.get_presentations(query, page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Google Slides: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/slides/create")
async def create_google_slide(
    slide_data: Dict[str, Any],
    request: Request,
    slides_service: GoogleSlidesService = Depends(get_google_slides_service)
):
    """Create a new Google Slide presentation"""
    try:
        title = slide_data.get("title")
        theme = slide_data.get("theme")
        folder_id = slide_data.get("folder_id")
        
        result = await slides_service.create_presentation(title, theme, folder_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create Google Slide: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/slides/{presentation_id}/slides")
async def get_presentation_slides(
    presentation_id: str,
    request: Request,
    slides_service: GoogleSlidesService = Depends(get_google_slides_service)
):
    """Get slides from presentation"""
    try:
        result = await slides_service.get_slides(presentation_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get presentation slides: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/slides/{presentation_id}/slides/add")
async def add_slide(
    presentation_id: str,
    slide_data: Dict[str, Any],
    request: Request,
    slides_service: GoogleSlidesService = Depends(get_google_slides_service)
):
    """Add a new slide to presentation"""
    try:
        slide_index = slide_data.get("slide_index")
        layout_id = slide_data.get("layout_id")
        
        result = await slides_service.add_slide(presentation_id, slide_index, layout_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to add slide: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Google Keep endpoints
@router.post("/keep/notes")
async def get_keep_notes(
    request: Request,
    keep_service: GoogleKeepService = Depends(get_google_keep_service)
):
    """Get Google Keep notes"""
    try:
        data = await request.json()
        query = data.get("query")
        page_size = data.get("page_size", 50)
        color_filter = data.get("color_filter")
        label_filter = data.get("label_filter")
        
        result = await keep_service.get_notes(query, page_size, color_filter, label_filter)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Google Keep notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/keep/notes/create")
async def create_keep_note(
    note_data: Dict[str, Any],
    request: Request,
    keep_service: GoogleKeepService = Depends(get_google_keep_service)
):
    """Create a new Google Keep note"""
    try:
        title = note_data.get("title")
        content = note_data.get("content")
        color = note_data.get("color")
        labels = note_data.get("labels", [])
        reminder = note_data.get("reminder")
        checklist_items = note_data.get("checklist_items", [])
        
        result = await keep_service.create_note(title, content, color, labels, reminder, checklist_items)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create Google Keep note: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/keep/notes/{note_id}")
async def update_keep_note(
    note_id: str,
    note_data: Dict[str, Any],
    request: Request,
    keep_service: GoogleKeepService = Depends(get_google_keep_service)
):
    """Update Google Keep note"""
    try:
        title = note_data.get("title")
        content = note_data.get("content")
        color = note_data.get("color")
        labels = note_data.get("labels")
        reminder = note_data.get("reminder")
        archived = note_data.get("archived")
        pinned = note_data.get("pinned")
        checklist_items = note_data.get("checklist_items")
        
        result = await keep_service.update_note(note_id, title, content, color, labels, reminder, archived, pinned, checklist_items)
        return result
        
    except Exception as e:
        logger.error(f"Failed to update Google Keep note: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/keep/notes/search")
async def search_keep_notes(
    search_data: Dict[str, Any],
    request: Request,
    keep_service: GoogleKeepService = Depends(get_google_keep_service)
):
    """Search Google Keep notes"""
    try:
        query = search_data.get("query")
        color_filter = search_data.get("color_filter")
        label_filter = search_data.get("label_filter")
        date_filter = search_data.get("date_filter")
        
        result = await keep_service.search_notes(query, color_filter, label_filter, date_filter)
        return result
        
    except Exception as e:
        logger.error(f"Failed to search Google Keep notes: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Google Tasks endpoints
@router.post("/tasks/lists")
async def get_task_lists(
    request: Request,
    tasks_service: GoogleTasksService = Depends(get_google_tasks_service)
):
    """Get Google Tasks lists"""
    try:
        data = await request.json()
        page_size = data.get("page_size", 50)
        
        result = await tasks_service.get_task_lists(page_size)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get task lists: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/lists/create")
async def create_task_list(
    list_data: Dict[str, Any],
    request: Request,
    tasks_service: GoogleTasksService = Depends(get_google_tasks_service)
):
    """Create a new task list"""
    try:
        title = list_data.get("title")
        
        result = await tasks_service.create_task_list(title)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create task list: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks")
async def get_tasks(
    request: Request,
    tasks_service: GoogleTasksService = Depends(get_google_tasks_service)
):
    """Get Google Tasks"""
    try:
        data = await request.json()
        task_list_id = data.get("task_list_id")
        show_completed = data.get("show_completed", True)
        show_hidden = data.get("show_hidden", False)
        max_results = data.get("max_results", 100)
        
        result = await tasks_service.get_tasks(task_list_id, show_completed, show_hidden, max_results)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/create")
async def create_task(
    task_data: Dict[str, Any],
    request: Request,
    tasks_service: GoogleTasksService = Depends(get_google_tasks_service)
):
    """Create a new task"""
    try:
        task_list_id = task_data.get("task_list_id")
        title = task_data.get("title")
        notes = task_data.get("notes")
        due = task_data.get("due")
        parent = task_data.get("parent")
        
        result = await tasks_service.create_task(task_list_id, title, notes, due, parent)
        return result
        
    except Exception as e:
        logger.error(f"Failed to create task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/tasks/{task_id}/complete")
async def complete_task(
    task_id: str,
    task_data: Dict[str, Any],
    request: Request,
    tasks_service: GoogleTasksService = Depends(get_google_tasks_service)
):
    """Complete a task"""
    try:
        task_list_id = task_data.get("task_list_id")
        
        result = await tasks_service.complete_task(task_list_id, task_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to complete task: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/status")
async def get_services_status():
    """Get status of all Google Workspace services"""
    try:
        services_status = {
            "google_docs": "available",
            "google_sheets": "available",
            "google_slides": "available",
            "google_keep": "available",
            "google_tasks": "available",
            "google_drive": "available",  # Already implemented
            "gmail": "available",         # Already implemented
            "google_calendar": "available" # Already implemented
        }
        
        return {
            "success": True,
            "services": services_status,
            "overall_status": "healthy"
        }
        
    except Exception as e:
        logger.error(f"Failed to get services status: {e}")
        return {
            "success": False,
            "error": str(e)
        }

@router.get("/dashboard/summary")
async def get_dashboard_summary(
    request: Request,
    docs_service: GoogleDocsService = Depends(get_google_docs_service),
    sheets_service: GoogleSheetsService = Depends(get_google_sheets_service),
    slides_service: GoogleSlidesService = Depends(get_google_slides_service),
    keep_service: GoogleKeepService = Depends(get_google_keep_service),
    tasks_service: GoogleTasksService = Depends(get_google_tasks_service)
):
    """Get comprehensive Google Workspace dashboard summary"""
    try:
        # Get data from all services
        docs_result = await docs_service.get_documents()
        sheets_result = await sheets_service.get_spreadsheets()
        slides_result = await slides_service.get_presentations()
        keep_result = await keep_service.get_notes()
        tasks_result = await tasks_service.get_tasks()
        
        # Calculate summary statistics
        summary = {
            "documents": {
                "total": len(docs_result.get("data", [])) if docs_result.get("success") else 0,
                "recent": 0  # Could calculate recent docs
            },
            "spreadsheets": {
                "total": len(sheets_result.get("data", [])) if sheets_result.get("success") else 0,
                "recent": 0
            },
            "presentations": {
                "total": len(slides_result.get("data", [])) if slides_result.get("success") else 0,
                "recent": 0
            },
            "notes": {
                "total": len(keep_result.get("data", [])) if keep_result.get("success") else 0,
                "pinned": 0,  # Could calculate pinned notes
                "archived": 0
            },
            "tasks": {
                "total": len(tasks_result.get("data", [])) if tasks_result.get("success") else 0,
                "completed": 0,  # Could calculate completed tasks
                "today": 0  # Could calculate today's tasks
            }
        }
        
        return {
            "success": True,
            "summary": summary,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
        
    except Exception as e:
        logger.error(f"Failed to get dashboard summary: {e}")
        return {
            "success": False,
            "error": str(e)
        }