import logging
from typing import List, Dict, Optional
from fastapi import APIRouter, Query, HTTPException
from pydantic import BaseModel
from datetime import datetime
import uuid

# Configure logging
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/marketplace", tags=["marketplace"])

# Pydantic models
class WorkflowTemplate(BaseModel):
    id: str
    name: str
    description: str
    category: str
    author: str
    version: str
    integrations: List[str]
    complexity: str
    created_at: str
    downloads: int
    rating: float

class TemplateResponse(BaseModel):
    success: bool
    data: List[WorkflowTemplate]
    total: int
    category: Optional[str] = None

class ImportResponse(BaseModel):
    success: bool
    message: str
    template_id: str
    workflow_id: Optional[str] = None

# Sample workflow templates
SAMPLE_TEMPLATES = [
    {
        "id": "lead-gen-automation",
        "name": "Lead Generation Automation",
        "description": "Automatically capture and qualify leads from multiple sources, assign to sales team, and update CRM.",
        "category": "Sales",
        "author": "ATOM Team",
        "version": "2.1.0",
        "integrations": ["HubSpot", "Slack", "Email"],
        "complexity": "Intermediate",
        "created_at": "2024-12-01T10:00:00Z",
        "downloads": 1247,
        "rating": 4.7
    },
    {
        "id": "expense-tracking",
        "name": "Expense Tracking & Reporting",
        "description": "Track expenses automatically, categorize spending, and generate monthly financial reports.",
        "category": "Finance",
        "author": "Finance Experts",
        "version": "1.8.3",
        "integrations": ["QuickBooks", "Email", "Slack"],
        "complexity": "Beginner",
        "created_at": "2024-11-15T14:30:00Z",
        "downloads": 892,
        "rating": 4.5
    },
    {
        "id": "social-media-scheduler",
        "name": "Social Media Content Scheduler",
        "description": "Schedule and publish content across multiple social platforms with AI-powered optimization.",
        "category": "Marketing",
        "author": "Marketing Pro",
        "version": "3.0.1",
        "integrations": ["Twitter", "LinkedIn", "Facebook", "Instagram"],
        "complexity": "Advanced",
        "created_at": "2024-12-05T09:15:00Z",
        "downloads": 2103,
        "rating": 4.8
    },
    {
        "id": "customer-support-automation",
        "name": "Customer Support Automation",
        "description": "Automatically route support tickets, suggest responses, and escalate complex issues.",
        "category": "Productivity",
        "author": "Support Masters",
        "version": "1.5.2",
        "integrations": ["Zendesk", "Slack", "Email"],
        "complexity": "Intermediate",
        "created_at": "2024-11-20T16:45:00Z",
        "downloads": 1567,
        "rating": 4.6
    },
    {
        "id": "code-deployment-pipeline",
        "name": "CI/CD Deployment Pipeline",
        "description": "Automated testing, building, and deployment pipeline for web applications.",
        "category": "Development",
        "author": "DevOps Team",
        "version": "2.3.0",
        "integrations": ["GitHub", "Docker", "AWS", "Slack"],
        "complexity": "Advanced",
        "created_at": "2024-12-03T11:20:00Z",
        "downloads": 743,
        "rating": 4.9
    },
    {
        "id": "invoice-management",
        "name": "Invoice Processing Automation",
        "description": "Automatically extract data from invoices, approve payments, and update accounting records.",
        "category": "Finance",
        "author": "Finance Automation Co",
        "version": "1.9.1",
        "integrations": ["QuickBooks", "Email", "OCR Service"],
        "complexity": "Intermediate",
        "created_at": "2024-11-28T13:10:00Z",
        "downloads": 634,
        "rating": 4.4
    },
    {
        "id": "email-campaign-tracker",
        "name": "Email Campaign Analytics",
        "description": "Track email campaign performance, analyze engagement metrics, and optimize delivery times.",
        "category": "Marketing",
        "author": "Email Marketing Pro",
        "version": "2.0.4",
        "integrations": ["Mailchimp", "Google Analytics", "Slack"],
        "complexity": "Beginner",
        "created_at": "2024-12-07T10:30:00Z",
        "downloads": 1821,
        "rating": 4.7
    },
    {
        "id": "project-status-reporter",
        "name": "Project Status Reporter",
        "description": "Automatically collect project updates from team members and generate status reports.",
        "category": "Productivity",
        "author": "PM Tools",
        "version": "1.4.0",
        "integrations": ["Jira", "Slack", "Email"],
        "complexity": "Beginner",
        "created_at": "2024-11-25T15:40:00Z",
        "downloads": 987,
        "rating": 4.3
    }
]

@router.get("/templates", response_model=TemplateResponse)
async def get_templates(
    category: Optional[str] = Query(None, description="Filter by category"),
    search: Optional[str] = Query(None, description="Search by name or description"),
    complexity: Optional[str] = Query(None, description="Filter by complexity level"),
    sort_by: str = Query("downloads", description="Sort by field"),
    limit: int = Query(50, le=100, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip")
):
    """Get workflow templates with optional filtering and sorting"""
    try:
        # Start with sample templates
        templates = SAMPLE_TEMPLATES.copy()

        # Apply filters
        if category:
            templates = [t for t in templates if t["category"].lower() == category.lower()]

        if complexity:
            templates = [t for t in templates if t["complexity"].lower() == complexity.lower()]

        if search:
            search_lower = search.lower()
            templates = [t for t in templates if
                        search_lower in t["name"].lower() or
                        search_lower in t["description"].lower()]

        # Sort templates
        reverse_sort = sort_by in ["downloads", "rating", "created_at"]
        templates.sort(key=lambda x: x.get(sort_by, 0), reverse=reverse_sort)

        # Apply pagination
        total = len(templates)
        paginated_templates = templates[offset:offset + limit]

        # Convert to Pydantic models
        template_models = [WorkflowTemplate(**t) for t in paginated_templates]

        logger.info(f"Retrieved {len(template_models)} templates (total: {total})")

        return TemplateResponse(
            success=True,
            data=template_models,
            total=total,
            category=category
        )

    except Exception as e:
        logger.error(f"Error fetching templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch templates")

@router.get("/templates/{template_id}", response_model=WorkflowTemplate)
async def get_template(template_id: str):
    """Get a specific template by ID"""
    try:
        template = next((t for t in SAMPLE_TEMPLATES if t["id"] == template_id), None)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        return WorkflowTemplate(**template)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching template {template_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch template")

@router.post("/templates/{template_id}/import", response_model=ImportResponse)
async def import_template(template_id: str):
    """Import a workflow template"""
    try:
        # Check if template exists
        template = next((t for t in SAMPLE_TEMPLATES if t["id"] == template_id), None)
        if not template:
            raise HTTPException(status_code=404, detail="Template not found")

        # Simulate import process
        workflow_id = f"workflow_{uuid.uuid4().hex[:8]}"

        # In a real implementation, this would:
        # 1. Create the workflow in the database
        # 2. Set up the automation steps
        # 3. Configure integrations
        # 4. Initialize any required resources

        logger.info(f"Imported template {template_id} as workflow {workflow_id}")

        return ImportResponse(
            success=True,
            message=f"Successfully imported '{template['name']}' workflow",
            template_id=template_id,
            workflow_id=workflow_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error importing template {template_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to import template")

@router.get("/categories")
async def get_categories():
    """Get all available categories"""
    try:
        categories = list(set(t["category"] for t in SAMPLE_TEMPLATES))
        categories.sort()

        return {
            "success": True,
            "data": categories,
            "total": len(categories)
        }

    except Exception as e:
        logger.error(f"Error fetching categories: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch categories")

@router.get("/search")
async def search_templates(
    q: str = Query(..., description="Search query"),
    category: Optional[str] = Query(None),
    complexity: Optional[str] = Query(None),
    limit: int = Query(20, le=50)
):
    """Search templates with advanced filtering"""
    return await get_templates(
        category=category,
        complexity=complexity,
        search=q,
        limit=limit,
        offset=0,
        sort_by="rating"
    )

@router.get("/featured")
async def get_featured_templates():
    """Get featured/highlighted templates"""
    try:
        # Return top rated and most downloaded templates
        featured = sorted(
            SAMPLE_TEMPLATES.copy(),
            key=lambda x: (x["rating"] * 0.6 + (x["downloads"] / 1000) * 0.4),
            reverse=True
        )[:5]

        template_models = [WorkflowTemplate(**t) for t in featured]

        return {
            "success": True,
            "data": template_models,
            "total": len(template_models)
        }

    except Exception as e:
        logger.error(f"Error fetching featured templates: {str(e)}")
        raise HTTPException(status_code=500, detail="Failed to fetch featured templates")