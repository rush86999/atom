"""
Tableau API Routes
Complete Tableau integration endpoints for the ATOM platform
"""

import json
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

# Configure logging
logger = logging.getLogger(__name__)

# Initialize router
router = APIRouter(prefix="/tableau", tags=["tableau"])


# Pydantic models for Tableau
class TableauAuthRequest(BaseModel):
    code: str
    redirect_uri: str


class TableauWorkbook(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    project_id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    content_url: Optional[str] = None
    show_tabs: bool = False
    size: Optional[int] = None
    tags: List[str] = []


class TableauDatasource(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    project_id: str
    owner_id: str
    created_at: datetime
    updated_at: datetime
    content_url: Optional[str] = None
    has_extracts: bool = False
    is_certified: bool = False
    tags: List[str] = []


class TableauView(BaseModel):
    id: str
    name: str
    content_url: str
    created_at: datetime
    updated_at: datetime
    owner_id: str
    workbook_id: str
    view_url_name: str
    tags: List[str] = []


class TableauProject(BaseModel):
    id: str
    name: str
    description: Optional[str] = None
    parent_project_id: Optional[str] = None
    owner_id: str
    created_at: datetime
    updated_at: datetime


class TableauUser(BaseModel):
    id: str
    email: str
    name: str
    site_role: str
    last_login: Optional[datetime] = None
    external_auth_user_id: Optional[str] = None


class TableauSearchRequest(BaseModel):
    query: str
    types: List[str] = ["workbook", "view", "datasource"]
    limit: int = 50
    offset: int = 0


class TableauSearchResponse(BaseModel):
    results: List[Dict[str, Any]]
    total_count: int
    has_more: bool


# Mock service for development
class TableauService:
    def __init__(self):
        self.base_url = "https://10ax.online.tableau.com/api/3.21"
        self.access_token = None
        self.site_id = None

    async def authenticate(self, auth_request: TableauAuthRequest) -> Dict[str, Any]:
        """Authenticate with Tableau using OAuth 2.0"""
        try:
            # In a real implementation, this would exchange the code for tokens
            # For now, return mock tokens
            self.access_token = "mock_tableau_access_token"
            self.site_id = "mock_site_id"

            return {
                "access_token": self.access_token,
                "token_type": "bearer",
                "expires_in": 3600,
                "refresh_token": "mock_refresh_token",
                "site_id": self.site_id,
            }
        except Exception as e:
            logger.error(f"Tableau authentication failed: {str(e)}")
            raise HTTPException(status_code=401, detail="Tableau authentication failed")

    async def get_workbooks(
        self, limit: int = 100, offset: int = 0
    ) -> List[TableauWorkbook]:
        """Get list of workbooks"""
        try:
            # Mock data for development
            workbooks = []
            for i in range(10):
                workbooks.append(
                    TableauWorkbook(
                        id=f"workbook_{i}",
                        name=f"Sample Workbook {i}",
                        description=f"Description for workbook {i}",
                        project_id="project_1",
                        owner_id="user_1",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        content_url=f"/workbooks/workbook_{i}",
                        show_tabs=True,
                        size=1024 * (i + 1),
                        tags=["sample", "demo"],
                    )
                )
            return workbooks
        except Exception as e:
            logger.error(f"Failed to get workbooks: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch workbooks")

    async def get_datasources(
        self, limit: int = 100, offset: int = 0
    ) -> List[TableauDatasource]:
        """Get list of datasources"""
        try:
            # Mock data for development
            datasources = []
            for i in range(10):
                datasources.append(
                    TableauDatasource(
                        id=f"datasource_{i}",
                        name=f"Sample Datasource {i}",
                        description=f"Description for datasource {i}",
                        project_id="project_1",
                        owner_id="user_1",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        content_url=f"/datasources/datasource_{i}",
                        has_extracts=(i % 2 == 0),
                        is_certified=(i % 3 == 0),
                        tags=["sample", "demo"],
                    )
                )
            return datasources
        except Exception as e:
            logger.error(f"Failed to get datasources: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch datasources")

    async def get_views(self, limit: int = 100, offset: int = 0) -> List[TableauView]:
        """Get list of views"""
        try:
            # Mock data for development
            views = []
            for i in range(10):
                views.append(
                    TableauView(
                        id=f"view_{i}",
                        name=f"Sample View {i}",
                        content_url=f"/views/view_{i}",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                        owner_id="user_1",
                        workbook_id=f"workbook_{i % 5}",
                        view_url_name=f"view_{i}",
                        tags=["sample", "demo"],
                    )
                )
            return views
        except Exception as e:
            logger.error(f"Failed to get views: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch views")

    async def get_projects(self) -> List[TableauProject]:
        """Get list of projects"""
        try:
            # Mock data for development
            projects = []
            for i in range(5):
                projects.append(
                    TableauProject(
                        id=f"project_{i}",
                        name=f"Sample Project {i}",
                        description=f"Description for project {i}",
                        parent_project_id=None if i == 0 else "project_0",
                        owner_id="user_1",
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc),
                    )
                )
            return projects
        except Exception as e:
            logger.error(f"Failed to get projects: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch projects")

    async def get_user_profile(self) -> TableauUser:
        """Get current user profile"""
        try:
            return TableauUser(
                id="user_1",
                email="user@example.com",
                name="Tableau User",
                site_role="SiteAdministrator",
                last_login=datetime.now(timezone.utc),
            )
        except Exception as e:
            logger.error(f"Failed to get user profile: {str(e)}")
            raise HTTPException(status_code=500, detail="Failed to fetch user profile")

    async def search_content(
        self, search_request: TableauSearchRequest
    ) -> TableauSearchResponse:
        """Search Tableau content"""
        try:
            # Mock search results
            results = []
            for i in range(min(10, search_request.limit)):
                result_type = search_request.types[i % len(search_request.types)]
                results.append(
                    {
                        "id": f"{result_type}_{i}",
                        "name": f"Sample {result_type.title()} {i}",
                        "type": result_type,
                        "description": f"Description for {result_type} {i}",
                        "project_id": "project_1",
                        "owner_id": "user_1",
                        "created_at": datetime.now(timezone.utc).isoformat(),
                        "updated_at": datetime.now(timezone.utc).isoformat(),
                    }
                )

            return TableauSearchResponse(
                results=results,
                total_count=len(results),
                has_more=len(results) >= search_request.limit,
            )
        except Exception as e:
            logger.error(f"Search failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Search failed")

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Tableau service"""
        try:
            return {
                "status": "healthy",
                "service": "tableau",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            logger.error(f"Health check failed: {str(e)}")
            raise HTTPException(status_code=500, detail="Health check failed")


# Initialize service
tableau_service = TableauService()


# API Routes
@router.post("/auth")
async def tableau_auth(auth_request: TableauAuthRequest):
    """Authenticate with Tableau"""
    try:
        result = await tableau_service.authenticate(auth_request)
        return {"success": True, "data": result}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Tableau auth error: {str(e)}")
        raise HTTPException(status_code=500, detail="Authentication failed")


@router.get("/workbooks")
async def get_workbooks(
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)
):
    """Get Tableau workbooks"""
    try:
        workbooks = await tableau_service.get_workbooks(limit, offset)
        return {"success": True, "data": workbooks, "count": len(workbooks)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get workbooks: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch workbooks")


@router.get("/datasources")
async def get_datasources(
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)
):
    """Get Tableau datasources"""
    try:
        datasources = await tableau_service.get_datasources(limit, offset)
        return {"success": True, "data": datasources, "count": len(datasources)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get datasources: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch datasources")


@router.get("/views")
async def get_views(
    limit: int = Query(100, ge=1, le=1000), offset: int = Query(0, ge=0)
):
    """Get Tableau views"""
    try:
        views = await tableau_service.get_views(limit, offset)
        return {"success": True, "data": views, "count": len(views)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get views: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch views")


@router.get("/projects")
async def get_projects():
    """Get Tableau projects"""
    try:
        projects = await tableau_service.get_projects()
        return {"success": True, "data": projects, "count": len(projects)}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get projects: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch projects")


@router.get("/user")
async def get_user_profile():
    """Get current Tableau user profile"""
    try:
        user = await tableau_service.get_user_profile()
        return {"success": True, "data": user}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get user profile: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch user profile")


@router.post("/search")
async def search_content(search_request: TableauSearchRequest):
    """Search Tableau content"""
    try:
        results = await tableau_service.search_content(search_request)
        return {"success": True, "data": results}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Search failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Search failed")


@router.get("/health")
async def health_check():
    """Tableau service health check"""
    try:
        health = await tableau_service.health_check()
        return {"success": True, "data": health}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Health check failed: {str(e)}")
        raise HTTPException(status_code=500, detail="Health check failed")


# Error handlers
@router.get("/")
async def tableau_root():
    """Tableau integration root endpoint"""
    return {
        "message": "Tableau integration API",
        "version": "1.0.0",
        "endpoints": [
            "/auth",
            "/workbooks",
            "/datasources",
            "/views",
            "/projects",
            "/user",
            "/search",
            "/health",
        ],
    }
