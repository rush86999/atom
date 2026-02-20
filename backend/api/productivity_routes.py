"""
Productivity Integration REST API Endpoints

Provides OAuth flow and Notion workspace endpoints for productivity.
All endpoints require authentication via get_current_user dependency.

Notion OAuth Flow:
1. GET /integrations/notion/authorize - Get Notion OAuth URL
2. GET /integrations/notion/callback - OAuth callback (token exchange)

Notion Workspace:
- GET /productivity/notion/search - Search workspace for pages/databases
- GET /productivity/notion/databases - List all databases
- GET /productivity/notion/databases/{database_id} - Get database schema
- POST /productivity/notion/databases/{database_id}/query - Query database
- GET /productivity/notion/pages/{page_id} - Get page content
- POST /productivity/notion/pages - Create new page
- PATCH /productivity/notion/pages/{page_id} - Update page
- POST /productivity/notion/pages/{page_id}/blocks - Append content blocks
"""

import logging
from typing import Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.productivity.notion_service import NotionService
from tools.productivity_tool import NotionTool

from api.oauth_routes import get_current_user
from core.models import User

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/productivity", tags=["productivity", "integrations", "notion"])


# ============================================================================
# Request/Response Models
# ============================================================================

class AuthorizeResponse(BaseModel):
    """OAuth authorization URL response."""
    authorization_url: str
    provider: str = "notion"


class CallbackResponse(BaseModel):
    """OAuth callback response."""
    success: bool
    message: str
    workspace_id: Optional[str] = None
    workspace_name: Optional[str] = None
    workspace_icon: Optional[str] = None


class SearchRequest(BaseModel):
    """Workspace search request."""
    query: str = Field(..., min_length=1, description="Search query text")


class SearchResult(BaseModel):
    """Search result item."""
    id: str
    title: str
    type: str
    url: str
    parent_id: Optional[str] = None


class SearchResponse(BaseModel):
    """Search response."""
    success: bool
    query: str
    count: int
    results: List[SearchResult]


class DatabaseInfo(BaseModel):
    """Database information."""
    id: str
    title: str
    description: str
    url: str


class DatabasesResponse(BaseModel):
    """Databases list response."""
    success: bool
    count: int
    databases: List[DatabaseInfo]


class DatabaseSchemaResponse(BaseModel):
    """Database schema response."""
    success: bool
    database_id: str
    schema_data: Dict = Field(..., alias="schema", description="Database schema")


class QueryDatabaseRequest(BaseModel):
    """Database query request."""
    filter: Optional[Dict] = Field(None, description="Notion filter object")


class QueryDatabaseResponse(BaseModel):
    """Database query response."""
    success: bool
    database_id: str
    count: int
    pages: List[Dict]


class PageResponse(BaseModel):
    """Page content response."""
    success: bool
    page_id: str
    page: Dict


class CreatePageRequest(BaseModel):
    """Create page request."""
    database_id: str = Field(..., description="Parent database ID")
    properties: Dict = Field(..., description="Page properties")


class CreatePageResponse(BaseModel):
    """Create page response."""
    success: bool
    database_id: str
    page: Dict


class UpdatePageRequest(BaseModel):
    """Update page request."""
    properties: Dict = Field(..., description="Properties to update")


class UpdatePageResponse(BaseModel):
    """Update page response."""
    success: bool
    page_id: str
    page: Dict


class AppendBlocksRequest(BaseModel):
    """Append blocks request."""
    blocks: List[Dict] = Field(..., description="Content blocks to append")


class AppendBlocksResponse(BaseModel):
    """Append blocks response."""
    success: bool
    page_id: str
    result: Dict


class ErrorResponse(BaseModel):
    """Error response."""
    success: bool = False
    error: str
    detail: Optional[str] = None


# ============================================================================
# Notion OAuth Endpoints
# ============================================================================

@router.get(
    "/integrations/notion/authorize",
    response_model=AuthorizeResponse,
    summary="Get Notion OAuth authorization URL"
)
async def get_notion_authorization_url(
    redirect_uri: Optional[str] = Query(None, description="Override redirect URI"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate Notion OAuth authorization URL.

    User should visit this URL to authorize Atom to access their Notion workspace.
    After authorization, Notion will redirect to the callback URL with auth code.
    """
    try:
        service = NotionService(current_user.id)

        # Generate authorization URL with state parameter
        auth_url = await NotionService.get_authorization_url(
            user_id=current_user.id
        )

        return AuthorizeResponse(
            authorization_url=auth_url,
            provider="notion"
        )

    except Exception as e:
        logger.error(f"Failed to generate Notion authorization URL: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate authorization URL: {str(e)}"
        )


@router.get(
    "/integrations/notion/callback",
    response_model=CallbackResponse,
    summary="Notion OAuth callback"
)
async def notion_oauth_callback(
    code: str = Query(..., description="Authorization code from Notion"),
    state: Optional[str] = Query(None, description="State parameter for CSRF protection"),
    error: Optional[str] = Query(None, description="Error from Notion (if authorization failed)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    OAuth callback endpoint - exchanges authorization code for access token.

    Notion redirects user's browser here after they authorize Atom.
    This endpoint exchanges the temporary code for a permanent access token
    and stores it encrypted in the database.
    """
    # Check if user denied authorization
    if error:
        logger.warning(f"Notion OAuth denied by user: {error}")
        return CallbackResponse(
            success=False,
            message=f"Authorization denied: {error}"
        )

    try:
        # Exchange code for access token
        result = await NotionService.exchange_code_for_tokens(
            code=code,
            user_id=current_user.id
        )

        logger.info(
            "Notion OAuth completed successfully",
            user_id=current_user.id,
            workspace_id=result.get("workspace_id")
        )

        return CallbackResponse(
            success=True,
            message="Successfully connected to Notion workspace",
            workspace_id=result.get("workspace_id"),
            workspace_name=result.get("workspace_name"),
            workspace_icon=result.get("workspace_icon")
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Notion OAuth callback failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"OAuth callback failed: {str(e)}"
        )


# ============================================================================
# Notion Workspace Endpoints
# ============================================================================

@router.post(
    "/notion/search",
    response_model=SearchResponse,
    summary="Search Notion workspace"
)
async def search_notion_workspace(
    request: SearchRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Search Notion workspace for pages and databases matching query.

    Returns pages and databases with titles matching the search query.
    """
    try:
        service = NotionService(current_user.id)
        results = await service.search_workspace(request.query)

        return SearchResponse(
            success=True,
            query=request.query,
            count=len(results),
            results=results
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions (401, 502, etc.)
        raise
    except Exception as e:
        logger.error(f"Notion search failed: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Search failed: {str(e)}"
        )


@router.get(
    "/notion/databases",
    response_model=DatabasesResponse,
    summary="List all Notion databases"
)
async def list_notion_databases(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    List all databases in the user's Notion workspace.

    Returns database IDs, titles, descriptions, and URLs.
    """
    try:
        service = NotionService(current_user.id)
        databases = await service.list_databases()

        return DatabasesResponse(
            success=True,
            count=len(databases),
            databases=databases
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to list Notion databases: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to list databases: {str(e)}"
        )


# ============================================================================
# Notion Database Endpoints
# ============================================================================

@router.get(
    "/notion/databases/{database_id}",
    response_model=DatabaseSchemaResponse,
    summary="Get Notion database schema"
)
async def get_notion_database_schema(
    database_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get database schema including properties and their types.

    Returns property names, types (title, text, number, date, select, etc.),
    and database metadata.
    """
    try:
        service = NotionService(current_user.id)
        schema = await service.get_database_schema(database_id)

        return DatabaseSchemaResponse(
            success=True,
            database_id=database_id,
            schema_data=schema
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions (404, etc.)
        raise
    except Exception as e:
        logger.error(f"Failed to get database schema: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get database schema: {str(e)}"
        )


@router.post(
    "/notion/databases/{database_id}/query",
    response_model=QueryDatabaseResponse,
    summary="Query Notion database"
)
async def query_notion_database(
    database_id: str,
    request: QueryDatabaseRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Query Notion database with optional filter.

    Returns all pages matching the filter. If no filter provided,
    returns all pages in the database.

    Filter format follows Notion API specification:
    https://developers.notion.com/reference/post-database-query
    """
    try:
        service = NotionService(current_user.id)
        pages = await service.query_database(
            database_id=database_id,
            filter=request.filter
        )

        return QueryDatabaseResponse(
            success=True,
            database_id=database_id,
            count=len(pages),
            pages=pages
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to query database: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Database query failed: {str(e)}"
        )


# ============================================================================
# Notion Page Endpoints
# ============================================================================

@router.get(
    "/notion/pages/{page_id}",
    response_model=PageResponse,
    summary="Get Notion page content"
)
async def get_notion_page(
    page_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get Notion page content including properties and blocks.

    Returns page properties and all content blocks (paragraphs,
    headings, lists, code blocks, etc.).
    """
    try:
        service = NotionService(current_user.id)
        page = await service.get_page(page_id)

        return PageResponse(
            success=True,
            page_id=page_id,
            page=page
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to get page: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get page: {str(e)}"
        )


@router.post(
    "/notion/pages",
    response_model=CreatePageResponse,
    summary="Create Notion page"
)
async def create_notion_page(
    request: CreatePageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Create new page in Notion database.

    Properties must match database schema (see GET /databases/{id} endpoint).
    """
    try:
        service = NotionService(current_user.id)
        page = await service.create_page(
            database_id=request.database_id,
            properties=request.properties
        )

        return CreatePageResponse(
            success=True,
            database_id=request.database_id,
            page=page
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to create page: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create page: {str(e)}"
        )


@router.patch(
    "/notion/pages/{page_id}",
    response_model=UpdatePageResponse,
    summary="Update Notion page"
)
async def update_notion_page(
    page_id: str,
    request: UpdatePageRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Update Notion page properties.

    Only updates properties specified in request. Partial updates allowed.
    """
    try:
        service = NotionService(current_user.id)
        page = await service.update_page(
            page_id=page_id,
            properties=request.properties
        )

        return UpdatePageResponse(
            success=True,
            page_id=page_id,
            page=page
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to update page: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to update page: {str(e)}"
        )


@router.post(
    "/notion/pages/{page_id}/blocks",
    response_model=AppendBlocksResponse,
    summary="Append content blocks to Notion page"
)
async def append_notion_page_blocks(
    page_id: str,
    request: AppendBlocksRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Append content blocks to Notion page.

    Supported block types:
    - paragraph, heading_1, heading_2, heading_3
    - bulleted_list_item, numbered_list_item
    - to_do (checkbox)
    - code
    - quote
    - divider
    - callout

    See Notion API docs for block object format:
    https://developers.notion.com/reference/block
    """
    try:
        service = NotionService(current_user.id)
        result = await service.append_page_blocks(
            page_id=page_id,
            blocks=request.blocks
        )

        return AppendBlocksResponse(
            success=True,
            page_id=page_id,
            result=result
        )

    except HTTPException as e:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Failed to append blocks: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Failed to append blocks: {str(e)}"
        )
