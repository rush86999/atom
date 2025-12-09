"""
LUX Model Marketplace API Routes
Endpoints for distributing and managing LUX models and templates
"""

import logging
from typing import Dict, List, Optional, Any
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from ai.lux_marketplace import marketplace, MarketplaceModel, ModelType, ModelCategory
from ai.lux_marketplace import AutomationTemplate
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/atom/lux/marketplace", tags=["LUX Marketplace"])

# Response models
class ModelResponse(BaseModel):
    success: bool
    models: List[Dict[str, Any]]
    total: int
    category: Optional[str] = None

class ModelDetailResponse(BaseModel):
    success: bool
    model: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

class DownloadResponse(BaseModel):
    success: bool
    model_id: str
    path: Optional[str] = None
    size: Optional[int] = None
    message: Optional[str] = None
    error: Optional[str] = None

class TemplateResponse(BaseModel):
    success: bool
    templates: List[Dict[str, Any]]
    total: int
    category: Optional[str] = None

class SearchRequest(BaseModel):
    query: str
    filters: Optional[Dict[str, Any]] = None
    limit: int = 20
    offset: int = 0

class RatingRequest(BaseModel):
    rating: float
    review: Optional[str] = None

class UploadRequest(BaseModel):
    name: str
    description: str
    version: str
    model_type: str
    category: str
    price: float
    tags: List[str]
    capabilities: List[str]
    requirements: Dict[str, Any]
    demo_video_url: Optional[str] = None
    documentation_url: Optional[str] = None

@router.get("/models", response_model=ModelResponse)
async def get_models(
    category: Optional[str] = None,
    model_type: Optional[str] = None,
    min_price: Optional[float] = None,
    max_price: Optional[float] = None
):
    """
    Get available LUX models from marketplace
    """
    try:
        # Convert string enums to enum objects
        category_enum = None
        if category:
            try:
                category_enum = ModelCategory(category)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category: {category}")

        type_enum = None
        if model_type:
            try:
                type_enum = ModelType(model_type)
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid model type: {model_type}")

        # Get models with filters
        models = marketplace.get_available_models(
            category=category_enum,
            model_type=type_enum,
            price_range=(min_price, max_price) if min_price is not None and max_price is not None else None
        )

        # Convert to dict for response
        model_dicts = []
        for model in models:
            model_dict = {
                "id": model.id,
                "name": model.name,
                "description": model.description,
                "author": model.author,
                "version": model.version,
                "model_type": model.model_type.value,
                "category": model.category.value,
                "price": model.price,
                "rating": model.rating,
                "downloads": model.downloads,
                "tags": model.tags,
                "capabilities": model.capabilities,
                "requirements": model.requirements,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
                "file_size": model.file_size,
                "checksum": model.checksum,
                "demo_video_url": model.demo_video_url,
                "documentation_url": model.documentation_url
            }
            model_dicts.append(model_dict)

        return ModelResponse(
            success=True,
            models=model_dicts,
            total=len(model_dicts),
            category=category
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get models: {str(e)}")

@router.get("/models/featured", response_model=ModelResponse)
async def get_featured_models():
    """
    Get featured models for homepage
    """
    try:
        models = marketplace.get_featured_models()

        # Convert to dict for response
        model_dicts = []
        for model in models:
            model_dict = {
                "id": model.id,
                "name": model.name,
                "description": model.description,
                "author": model.author,
                "version": model.version,
                "model_type": model.model_type.value,
                "category": model.category.value,
                "price": model.price,
                "rating": model.rating,
                "downloads": model.downloads,
                "tags": model.tags,
                "capabilities": model.capabilities,
                "requirements": model.requirements,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
                "file_size": model.file_size,
                "checksum": model.checksum,
                "demo_video_url": model.demo_video_url,
                "documentation_url": model.documentation_url
            }
            model_dicts.append(model_dict)

        return ModelResponse(
            success=True,
            models=model_dicts,
            total=len(model_dicts),
            category="featured"
        )

    except Exception as e:
        logger.error(f"Failed to get featured models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get featured models: {str(e)}")

@router.get("/models/{model_id}", response_model=ModelDetailResponse)
async def get_model_details(model_id: str):
    """
    Get detailed information about a specific model
    """
    try:
        model = marketplace.get_model_details(model_id)
        if not model:
            return ModelDetailResponse(
                success=False,
                error=f"Model '{model_id}' not found"
            )

        model_dict = {
            "id": model.id,
            "name": model.name,
            "description": model.description,
            "author": model.author,
            "version": model.version,
            "model_type": model.model_type.value,
            "category": model.category.value,
            "price": model.price,
            "rating": model.rating,
            "downloads": model.downloads,
            "tags": model.tags,
            "capabilities": model.capabilities,
            "requirements": model.requirements,
            "created_at": model.created_at,
            "updated_at": model.updated_at,
            "file_size": model.file_size,
            "checksum": model.checksum,
            "demo_video_url": model.demo_video_url,
            "documentation_url": model.documentation_url
        }

        return ModelDetailResponse(
            success=True,
            model=model_dict
        )

    except Exception as e:
        logger.error(f"Failed to get model details: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get model details: {str(e)}")

@router.post("/models/{model_id}/download", response_model=DownloadResponse)
async def download_model(model_id: str, api_key: Optional[str] = None):
    """
    Download a model from marketplace
    """
    try:
        result = marketplace.download_model(model_id, api_key)

        return DownloadResponse(
            success=result.get("success", False),
            model_id=model_id,
            path=result.get("path"),
            size=result.get("size"),
            message=result.get("message"),
            error=result.get("error")
        )

    except Exception as e:
        logger.error(f"Failed to download model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to download model: {str(e)}")

@router.post("/models/{model_id}/rate")
async def rate_model(model_id: str, request: RatingRequest):
    """
    Rate a model
    """
    try:
        if not 1.0 <= request.rating <= 5.0:
            raise HTTPException(status_code=400, detail="Rating must be between 1.0 and 5.0")

        result = marketplace.rate_model(model_id, request.rating, request.review)

        if not result.get("success"):
            raise HTTPException(status_code=400, detail=result.get("error", "Rating failed"))

        return {
            "success": True,
            "model_id": model_id,
            "new_rating": request.rating,
            "message": result.get("message", "Rating submitted successfully")
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to rate model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to rate model: {str(e)}")

@router.post("/models/search", response_model=ModelResponse)
async def search_models(request: SearchRequest):
    """
    Search models in marketplace
    """
    try:
        # Convert filters to proper types
        filters = request.filters or {}
        if "category" in filters:
            try:
                filters["category"] = ModelCategory(filters["category"])
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid category filter: {filters['category']}")

        if "model_type" in filters:
            try:
                filters["model_type"] = ModelType(filters["model_type"])
            except ValueError:
                raise HTTPException(status_code=400, detail=f"Invalid model type filter: {filters['model_type']}")

        models = marketplace.search_models(request.query, filters)

        # Apply pagination
        start = request.offset
        end = start + request.limit
        paginated_models = models[start:end]

        # Convert to dict for response
        model_dicts = []
        for model in paginated_models:
            model_dict = {
                "id": model.id,
                "name": model.name,
                "description": model.description,
                "author": model.author,
                "version": model.version,
                "model_type": model.model_type.value,
                "category": model.category.value,
                "price": model.price,
                "rating": model.rating,
                "downloads": model.downloads,
                "tags": model.tags,
                "capabilities": model.capabilities,
                "requirements": model.requirements,
                "created_at": model.created_at,
                "updated_at": model.updated_at,
                "file_size": model.file_size,
                "checksum": model.checksum,
                "demo_video_url": model.demo_video_url,
                "documentation_url": model.documentation_url
            }
            model_dicts.append(model_dict)

        return ModelResponse(
            success=True,
            models=model_dicts,
            total=len(models),
            category=f"search:{request.query}"
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search models: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to search models: {str(e)}")

@router.get("/templates", response_model=TemplateResponse)
async def get_automation_templates(category: Optional[str] = None):
    """
    Get available automation templates
    """
    try:
        templates = marketplace.get_automation_templates(category)

        # Convert to dict for response
        template_dicts = []
        for template in templates:
            template_dict = {
                "id": template.id,
                "name": template.name,
                "description": template.description,
                "author": template.author,
                "category": template.category,
                "commands": template.commands,
                "parameters": template.parameters,
                "tags": template.tags,
                "rating": template.rating,
                "downloads": template.downloads,
                "created_at": template.created_at,
                "compatibility": template.compatibility
            }
            template_dicts.append(template_dict)

        return TemplateResponse(
            success=True,
            templates=template_dicts,
            total=len(template_dicts),
            category=category
        )

    except Exception as e:
        logger.error(f"Failed to get templates: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get templates: {str(e)}")

@router.post("/models/upload")
async def upload_model(
    file: UploadFile = File(...),
    api_key: str = Form(...),
    name: str = Form(...),
    description: str = Form(...),
    version: str = Form(...),
    model_type: str = Form(...),
    category: str = Form(...),
    price: float = Form(...),
    tags: str = Form(...),  # JSON string
    capabilities: str = Form(...),  # JSON string
    requirements: str = Form(...),  # JSON string
    demo_video_url: Optional[str] = Form(None),
    documentation_url: Optional[str] = Form(None)
):
    """
    Upload a new model to marketplace (for creators)
    """
    try:
        # Parse JSON fields
        import json
        tags_list = json.loads(tags)
        capabilities_list = json.loads(capabilities)
        requirements_dict = json.loads(requirements)

        model_data = {
            "name": name,
            "description": description,
            "version": version,
            "model_type": model_type,
            "category": category,
            "price": price,
            "tags": tags_list,
            "capabilities": capabilities_list,
            "requirements": requirements_dict,
            "demo_video_url": demo_video_url,
            "documentation_url": documentation_url
        }

        # Save uploaded file temporarily
        import tempfile
        with tempfile.NamedTemporaryFile(delete=False) as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name

        try:
            result = marketplace.upload_model(model_data, temp_file_path, api_key)

            if not result.get("success"):
                raise HTTPException(status_code=400, detail=result.get("error", "Upload failed"))

            return {
                "success": True,
                "model_id": result.get("model_id"),
                "message": result.get("message", "Model uploaded successfully"),
                "status": result.get("status", "pending_review")
            }

        finally:
            # Clean up temporary file
            import os
            os.unlink(temp_file_path)

    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON in form fields: {str(e)}")
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to upload model: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to upload model: {str(e)}")

@router.get("/categories")
async def get_marketplace_categories():
    """
    Get available marketplace categories
    """
    try:
        return {
            "success": True,
            "categories": [
                {"value": cat.value, "label": cat.value.title()}
                for cat in ModelCategory
            ],
            "model_types": [
                {"value": mt.value, "label": mt.value.replace("_", " ").title()}
                for mt in ModelType
            ]
        }

    except Exception as e:
        logger.error(f"Failed to get categories: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get categories: {str(e)}")

@router.get("/stats")
async def get_marketplace_stats():
    """
    Get marketplace statistics
    """
    try:
        models = marketplace.get_available_models()
        templates = marketplace.get_automation_templates()

        total_models = len(models)
        free_models = len([m for m in models if m.price == 0])
        paid_models = total_models - free_models
        total_downloads = sum(m.downloads for m in models)
        avg_rating = sum(m.rating for m in models) / total_models if total_models > 0 else 0

        category_counts = {}
        for model in models:
            cat = model.category.value
            category_counts[cat] = category_counts.get(cat, 0) + 1

        return {
            "success": True,
            "total_models": total_models,
            "free_models": free_models,
            "paid_models": paid_models,
            "total_templates": len(templates),
            "total_downloads": total_downloads,
            "average_rating": round(avg_rating, 2),
            "category_distribution": category_counts,
            "last_updated": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Failed to get marketplace stats: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get marketplace stats: {str(e)}")