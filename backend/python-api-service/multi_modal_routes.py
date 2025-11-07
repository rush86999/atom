"""
ATOM Multi-Modal AI Integration Routes
Complete API routes for multi-modal AI services integration
"""

import os
import json
import asyncio
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta
from fastapi import APIRouter, UploadFile, File, Form, HTTPException, Query, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
import base64
import io

# Multi-Modal Services
from vision_ai_service import create_vision_ai_service, VisionTask, VisionModel, VisionRequest
from audio_ai_service import create_audio_ai_service, AudioTask, AudioModel, AudioRequest
from cross_modal_ai_service import create_cross_modal_ai_service, CrossModalTask, CrossModalRequest
from multi_modal_workflow_engine import create_multi_modal_workflow_engine, WorkflowStatus, MultiModalContent, WorkflowExecution
from multi_modal_business_intelligence import create_multi_modal_business_intelligence, InsightType, TimeGranularity, AnalyticsRequest, BusinessInsight, MultimodalDashboard

# Existing Services
from advanced_ai_models_service import create_advanced_ai_models_service, AIModelType

# Create service instances
vision_ai_service = create_vision_ai_service()
audio_ai_service = create_audio_ai_service()
cross_modal_ai_service = create_cross_modal_ai_service()
workflow_engine = create_multi_modal_workflow_engine()
business_intelligence = create_multi_modal_business_intelligence()
advanced_ai_service = create_advanced_ai_models_service()

# Create router
router = APIRouter(prefix="/api/multimodal", tags=["multi-modal-ai"])

# Pydantic Models
class ImageAnalysisRequest(BaseModel):
    task_type: str = Field(default="image_analysis", description="Vision task type")
    model: str = Field(default="openai_vision", description="Vision model to use")
    text_prompt: Optional[str] = Field(default=None, description="Text prompt for analysis")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Processing options")

class AudioAnalysisRequest(BaseModel):
    task_type: str = Field(default="speech_recognition", description="Audio task type")
    model: str = Field(default="openai_whisper", description="Audio model to use")
    language: Optional[str] = Field(default="en", description="Language for transcription")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Processing options")

class CrossModalAnalysisRequest(BaseModel):
    task_type: str = Field(default="content_understanding", description="Cross-modal task type")
    text_prompt: Optional[str] = Field(default=None, description="Text prompt for analysis")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Processing options")

class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    triggers: List[Dict[str, Any]] = Field(..., description="Workflow triggers")
    actions: List[Dict[str, Any]] = Field(..., description="Workflow actions")
    enabled: bool = Field(default=True, description="Whether workflow is enabled")
    priority: int = Field(default=5, description="Workflow priority")

class WorkflowUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, description="Updated workflow name")
    description: Optional[str] = Field(default=None, description="Updated workflow description")
    enabled: Optional[bool] = Field(default=None, description="Updated enabled status")
    triggers: Optional[List[Dict[str, Any]]] = Field(default=None, description="Updated triggers")
    actions: Optional[List[Dict[str, Any]]] = Field(default=None, description="Updated actions")

class AnalyticsRequest(BaseModel):
    insight_types: List[str] = Field(default=["trend_analysis", "anomaly_detection"], description="Types of insights to generate")
    time_window_start: str = Field(..., description="Start of time window (ISO format)")
    time_window_end: str = Field(..., description="End of time window (ISO format)")
    granularity: str = Field(default="hour", description="Time granularity")
    filters: Optional[Dict[str, Any]] = Field(default=None, description="Analysis filters")
    kpi_names: List[str] = Field(default=["text_sentiment", "insight_confidence"], description="KPIs to analyze")
    modalities: List[str] = Field(default=["text", "image", "audio"], description="Modalities to include")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Analysis options")

class DashboardCreateRequest(BaseModel):
    name: str = Field(..., description="Dashboard name")
    description: str = Field(..., description="Dashboard description")
    widgets: List[Dict[str, Any]] = Field(..., description="Dashboard widgets")
    data_sources: List[str] = Field(default=[], description="Data sources for dashboard")
    time_filters: Optional[Dict[str, Any]] = Field(default=None, description="Time filters")
    kpi_definitions: Optional[Dict[str, Any]] = Field(default=None, description="KPI definitions")
    refresh_interval: Optional[int] = Field(default=None, description="Refresh interval in seconds")

# Vision AI Routes
@router.post("/vision/analyze", response_model=Dict[str, Any])
async def analyze_image(
    background_tasks: BackgroundTasks,
    image: UploadFile = File(...),
    task_type: str = Form(default="image_analysis"),
    model: str = Form(default="openai_vision"),
    text_prompt: Optional[str] = Form(default=None),
    context: Optional[str] = Form(default=None)
):
    """Analyze image with vision AI"""
    try:
        # Read image data
        image_data = await image.read()
        
        # Parse context
        context_data = json.loads(context) if context else {}
        
        # Create vision request
        vision_request = VisionRequest(
            request_id=str(uuid.uuid4()),
            task_type=VisionTask(task_type),
            vision_model=VisionModel(model),
            image_data=image_data,
            text_prompt=text_prompt,
            context=context_data
        )
        
        # Process vision request
        response = await vision_ai_service.process_vision_request(vision_request)
        
        return {
            "success": response.success,
            "results": response.results,
            "processing_time": response.processing_time,
            "cost": response.cost,
            "metadata": response.metadata,
            "timestamp": response.timestamp.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Image analysis failed: {str(e)}")

# Audio AI Routes
@router.post("/audio/analyze", response_model=Dict[str, Any])
async def analyze_audio(
    background_tasks: BackgroundTasks,
    audio: UploadFile = File(...),
    task_type: str = Form(default="speech_recognition"),
    model: str = Form(default="openai_whisper"),
    language: str = Form(default="en"),
    context: Optional[str] = Form(default=None)
):
    """Analyze audio with AI"""
    try:
        # Read audio data
        audio_data = await audio.read()
        
        # Parse context
        context_data = json.loads(context) if context else {}
        
        # Create audio request
        audio_request = AudioRequest(
            request_id=str(uuid.uuid4()),
            task_type=AudioTask(task_type),
            audio_model=AudioModel(model),
            audio_data=audio_data,
            language=language,
            context=context_data
        )
        
        # Process audio request
        response = await audio_ai_service.process_audio_request(audio_request)
        
        return {
            "success": response.success,
            "results": response.results,
            "processing_time": response.processing_time,
            "cost": response.cost,
            "metadata": response.metadata,
            "timestamp": response.timestamp.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Audio analysis failed: {str(e)}")

# Cross-Modal AI Routes
@router.post("/cross-modal/analyze", response_model=Dict[str, Any])
async def analyze_cross_modal(
    background_tasks: BackgroundTasks,
    task_type: str = Form(default="content_understanding"),
    text_prompt: Optional[str] = Form(default=None),
    text_data: Optional[UploadFile] = File(default=None),
    image_data: Optional[UploadFile] = File(default=None),
    audio_data: Optional[UploadFile] = File(default=None),
    video_data: Optional[UploadFile] = File(default=None),
    document_data: Optional[UploadFile] = File(default=None),
    context: Optional[str] = Form(default=None)
):
    """Analyze cross-modal content"""
    try:
        # Collect content modalities
        content_data = {}
        
        if text_data:
            content_data["text"] = (await text_data.read()).decode('utf-8')
        
        if image_data:
            content_data["image"] = await image_data.read()
        
        if audio_data:
            content_data["audio"] = await audio_data.read()
        
        if video_data:
            content_data["video"] = await video_data.read()
        
        if document_data:
            content_data["document"] = await document_data.read()
        
        # Parse context
        context_data = json.loads(context) if context else {}
        
        # Create cross-modal request
        cross_modal_request = CrossModalRequest(
            request_id=str(uuid.uuid4()),
            task_type=CrossModalTask(task_type),
            content_data=content_data,
            text_prompt=text_prompt,
            context=context_data
        )
        
        # Process cross-modal request
        response = await cross_modal_ai_service.process_cross_modal_request(cross_modal_request)
        
        return {
            "success": response.success,
            "insights": [asdict(insight) for insight in response.insights],
            "correlations": [asdict(correlation) for correlation in response.correlations],
            "concepts": [asdict(concept) for concept in response.concepts],
            "processing_time": response.processing_time,
            "cost": response.cost,
            "metadata": response.metadata,
            "timestamp": response.timestamp.isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Cross-modal analysis failed: {str(e)}")

# Workflow Engine Routes
@router.post("/workflows", response_model=Dict[str, Any])
async def create_workflow(workflow_request: WorkflowCreateRequest):
    """Create new multi-modal workflow"""
    try:
        # Convert to workflow objects
        from multi_modal_workflow_engine import WorkflowTrigger, WorkflowAction, MultiModalWorkflow
        
        triggers = [
            WorkflowTrigger(
                trigger_id=str(uuid.uuid4()),
                trigger_type=trigger["trigger_type"],
                content_modality=trigger.get("content_modality"),
                conditions=trigger.get("conditions", {}),
                parameters=trigger.get("parameters", {})
            )
            for trigger in workflow_request.triggers
        ]
        
        actions = [
            WorkflowAction(
                action_id=str(uuid.uuid4()),
                action_type=action["action_type"],
                parameters=action.get("parameters", {}),
                conditions=action.get("conditions", {})
            )
            for action in workflow_request.actions
        ]
        
        workflow = MultiModalWorkflow(
            workflow_id=str(uuid.uuid4()),
            name=workflow_request.name,
            description=workflow_request.description,
            triggers=triggers,
            actions=actions,
            enabled=workflow_request.enabled,
            priority=workflow_request.priority
        )
        
        # Create workflow
        workflow_id = await workflow_engine.create_workflow(workflow)
        
        return {
            "success": True,
            "workflow_id": workflow_id,
            "message": "Workflow created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow creation failed: {str(e)}")

@router.get("/workflows", response_model=List[Dict[str, Any]])
async def get_workflows():
    """Get all workflows"""
    try:
        workflows = workflow_engine.get_workflow_list()
        return workflows
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get workflows: {str(e)}")

@router.put("/workflows/{workflow_id}", response_model=Dict[str, Any])
async def update_workflow(workflow_id: str, updates: WorkflowUpdateRequest):
    """Update existing workflow"""
    try:
        # Convert to dict for update
        update_dict = {}
        if updates.name is not None:
            update_dict["name"] = updates.name
        if updates.description is not None:
            update_dict["description"] = updates.description
        if updates.enabled is not None:
            update_dict["enabled"] = updates.enabled
        if updates.triggers is not None:
            update_dict["triggers"] = updates.triggers
        if updates.actions is not None:
            update_dict["actions"] = updates.actions
        
        success = await workflow_engine.update_workflow(workflow_id, update_dict)
        
        return {
            "success": success,
            "message": "Workflow updated successfully" if success else "Workflow update failed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow update failed: {str(e)}")

@router.delete("/workflows/{workflow_id}", response_model=Dict[str, Any])
async def delete_workflow(workflow_id: str):
    """Delete workflow"""
    try:
        success = await workflow_engine.delete_workflow(workflow_id)
        
        return {
            "success": success,
            "message": "Workflow deleted successfully" if success else "Workflow deletion failed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow deletion failed: {str(e)}")

@router.post("/workflows/content", response_model=Dict[str, Any])
async def submit_workflow_content(
    background_tasks: BackgroundTasks,
    text_data: Optional[UploadFile] = File(default=None),
    image_data: Optional[UploadFile] = File(default=None),
    audio_data: Optional[UploadFile] = File(default=None),
    metadata: Optional[str] = Form(default=None)
):
    """Submit content for workflow processing"""
    try:
        # Collect content modalities
        content_modalities = {}
        
        if text_data:
            content_modalities["text"] = (await text_data.read()).decode('utf-8')
        
        if image_data:
            content_modalities["image"] = await image_data.read()
        
        if audio_data:
            content_modalities["audio"] = await audio_data.read()
        
        # Parse metadata
        metadata_data = json.loads(metadata) if metadata else {}
        
        # Create multimodal content
        content = MultiModalContent(
            content_id=str(uuid.uuid4()),
            modalities=content_modalities,
            metadata=metadata_data
        )
        
        # Submit content
        content_id = await workflow_engine.submit_content(content)
        
        return {
            "success": True,
            "content_id": content_id,
            "message": "Content submitted successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Content submission failed: {str(e)}")

@router.get("/workflows/executions", response_model=List[Dict[str, Any]])
async def get_workflow_executions(
    limit: int = Query(default=100, ge=1, le=1000),
    workflow_id: Optional[str] = Query(default=None)
):
    """Get workflow execution history"""
    try:
        executions = workflow_engine.get_execution_history(limit=limit, workflow_id=workflow_id)
        return executions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get executions: {str(e)}")

@router.get("/workflows/executions/active", response_model=List[Dict[str, Any]])
async def get_active_executions():
    """Get active workflow executions"""
    try:
        executions = workflow_engine.get_active_executions()
        return executions
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get active executions: {str(e)}")

@router.post("/workflows/executions/{execution_id}/cancel", response_model=Dict[str, Any])
async def cancel_execution(execution_id: str):
    """Cancel workflow execution"""
    try:
        success = await workflow_engine.cancel_execution(execution_id)
        
        return {
            "success": success,
            "message": "Execution cancelled successfully" if success else "Execution cancellation failed"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution cancellation failed: {str(e)}")

# Business Intelligence Routes
@router.post("/analytics/generate", response_model=Dict[str, Any])
async def generate_analytics(analytics_request: AnalyticsRequest):
    """Generate multi-modal business analytics"""
    try:
        # Convert time windows
        time_start = datetime.fromisoformat(analytics_request.time_window_start)
        time_end = datetime.fromisoformat(analytics_request.time_window_end)
        
        # Convert insight types
        insight_types = [InsightType(t) for t in analytics_request.insight_types]
        
        # Create analytics request
        request = AnalyticsRequest(
            request_id=str(uuid.uuid4()),
            insight_types=insight_types,
            time_window=(time_start, time_end),
            granularity=TimeGranularity(analytics_request.granularity),
            filters=analytics_request.filters or {},
            kpi_names=analytics_request.kpi_names,
            modalities=analytics_request.modalities,
            options=analytics_request.options or {}
        )
        
        # Generate analytics
        result = await business_intelligence.generate_analytics(request)
        
        return result
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Analytics generation failed: {str(e)}")

@router.post("/analytics/dashboards", response_model=Dict[str, Any])
async def create_dashboard(dashboard_request: DashboardCreateRequest):
    """Create multi-modal analytics dashboard"""
    try:
        # Create dashboard
        dashboard = MultimodalDashboard(
            dashboard_id=str(uuid.uuid4()),
            name=dashboard_request.name,
            description=dashboard_request.description,
            widgets=dashboard_request.widgets,
            data_sources=dashboard_request.data_sources,
            time_filters=dashboard_request.time_filters or {},
            kpi_definitions=dashboard_request.kpi_definitions or {},
            refresh_interval=dashboard_request.refresh_interval
        )
        
        # Create dashboard
        dashboard_id = await business_intelligence.create_dashboard(dashboard)
        
        return {
            "success": True,
            "dashboard_id": dashboard_id,
            "message": "Dashboard created successfully"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Dashboard creation failed: {str(e)}")

@router.get("/analytics/dashboards/{dashboard_id}/data", response_model=Dict[str, Any])
async def get_dashboard_data(dashboard_id: str):
    """Get real-time dashboard data"""
    try:
        dashboard_data = await business_intelligence.get_dashboard_data(dashboard_id)
        return dashboard_data
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get dashboard data: {str(e)}")

# Model Management Routes
@router.get("/models", response_model=Dict[str, Any])
async def get_available_models():
    """Get available models for all services"""
    try:
        vision_models = vision_ai_service.get_available_models()
        audio_models = audio_ai_service.get_available_models()
        cross_modal_models = cross_modal_ai_service.get_service_capabilities()
        
        return {
            "vision_models": vision_models,
            "audio_models": audio_models,
            "cross_modal_models": cross_modal_models,
            "total_models": vision_models.get("total_models", 0) + audio_models.get("total_models", 0)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get available models: {str(e)}")

# Service Status Routes
@router.get("/status", response_model=Dict[str, Any])
async def get_service_status():
    """Get comprehensive service status"""
    try:
        vision_status = vision_ai_service.get_available_models()
        audio_status = audio_ai_service.get_available_models()
        cross_modal_status = cross_modal_ai_service.get_service_capabilities()
        workflow_status = workflow_engine.get_engine_status()
        bi_status = business_intelligence.get_service_status()
        
        return {
            "vision_ai": {
                "available": vision_status.get("total_models", 0) > 0,
                "models": vision_status.get("total_models", 0),
                "performance": vision_status.get("performance_metrics", {})
            },
            "audio_ai": {
                "available": audio_status.get("total_models", 0) > 0,
                "models": audio_status.get("total_models", 0),
                "performance": audio_status.get("performance_metrics", {})
            },
            "cross_modal_ai": {
                "available": len(cross_modal_status.get("supported_tasks", [])) > 0,
                "tasks": len(cross_modal_status.get("supported_tasks", [])),
                "modalities": cross_modal_status.get("supported_modalities", [])
            },
            "workflow_engine": {
                "status": workflow_status.get("status"),
                "workflows": workflow_status.get("total_workflows", 0),
                "active_executions": workflow_status.get("active_executions", 0),
                "content_items": workflow_status.get("total_content", 0)
            },
            "business_intelligence": {
                "status": bi_status.get("status"),
                "data_points": bi_status.get("data_points", 0),
                "insights": bi_status.get("insights", 0),
                "dashboards": bi_status.get("dashboards", 0)
            },
            "overall_status": "healthy" if all([
                vision_status.get("total_models", 0) > 0,
                audio_status.get("total_models", 0) > 0,
                len(cross_modal_status.get("supported_tasks", [])) > 0
            ]) else "degraded",
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get service status: {str(e)}")

# Batch Processing Routes
@router.post("/batch/process", response_model=Dict[str, Any])
async def process_batch(
    background_tasks: BackgroundTasks,
    files: List[UploadFile] = File(...),
    task_types: str = Form(default='["image_analysis","audio_analysis"]'),
    models: Optional[str] = Form(default=None),
    parallel: bool = Form(default=True)
):
    """Process multiple files in batch"""
    try:
        # Parse parameters
        task_types_list = json.loads(task_types)
        models_dict = json.loads(models) if models else {}
        
        batch_results = []
        
        async def process_file(file: UploadFile, task_type: str, model: str) -> Dict[str, Any]:
            try:
                file_data = await file.read()
                
                if "image" in task_type.lower():
                    vision_request = VisionRequest(
                        request_id=str(uuid.uuid4()),
                        task_type=VisionTask.IMAGE_ANALYSIS,
                        vision_model=VisionModel(model) if model else VisionModel.OPENAI_VISION,
                        image_data=file_data
                    )
                    response = await vision_ai_service.process_vision_request(vision_request)
                    return {
                        "id": file.filename,
                        "results": response.results if response.success else {"error": response.results},
                        "success": response.success,
                        "processing_time": response.processing_time
                    }
                
                elif "audio" in task_type.lower():
                    audio_request = AudioRequest(
                        request_id=str(uuid.uuid4()),
                        task_type=AudioTask.AUDIO_ANALYSIS,
                        audio_model=AudioModel(model) if model else AudioModel.WHISPER_LOCAL,
                        audio_data=file_data
                    )
                    response = await audio_ai_service.process_audio_request(audio_request)
                    return {
                        "id": file.filename,
                        "results": response.results if response.success else {"error": response.results},
                        "success": response.success,
                        "processing_time": response.processing_time
                    }
                
                return {
                    "id": file.filename,
                    "results": {"error": f"Unsupported task type: {task_type}"},
                    "success": False,
                    "processing_time": 0.0
                }
                
            except Exception as e:
                return {
                    "id": file.filename,
                    "results": {"error": str(e)},
                    "success": False,
                    "processing_time": 0.0
                }
        
        # Process files
        if parallel:
            # Process in parallel
            tasks = []
            for file in files:
                for task_type in task_types_list:
                    model = models_dict.get(task_type, "")
                    tasks.append(process_file(file, task_type, model))
            
            batch_results = await asyncio.gather(*tasks)
        else:
            # Process sequentially
            for file in files:
                for task_type in task_types_list:
                    model = models_dict.get(task_type, "")
                    result = await process_file(file, task_type, model)
                    batch_results.append(result)
        
        # Calculate summary
        total_files = len(files)
        total_tasks = len(files) * len(task_types_list)
        successful_tasks = sum(1 for result in batch_results if result["success"])
        total_processing_time = sum(result["processing_time"] for result in batch_results)
        
        return {
            "success": True,
            "results": batch_results,
            "summary": {
                "total_files": total_files,
                "total_tasks": total_tasks,
                "successful_tasks": successful_tasks,
                "failed_tasks": total_tasks - successful_tasks,
                "success_rate": successful_tasks / total_tasks if total_tasks > 0 else 0,
                "total_processing_time": total_processing_time,
                "average_processing_time": total_processing_time / total_tasks if total_tasks > 0 else 0
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Batch processing failed: {str(e)}")

# Health Check Route
@router.get("/health", response_model=Dict[str, Any])
async def health_check():
    """Multi-modal AI service health check"""
    try:
        # Check individual services
        vision_models = vision_ai_service.get_available_models()
        audio_models = audio_ai_service.get_available_models()
        workflow_status = workflow_engine.get_engine_status()
        bi_status = business_intelligence.get_service_status()
        
        services_healthy = all([
            vision_models.get("total_models", 0) > 0,
            audio_models.get("total_models", 0) > 0,
            workflow_status.get("status") == "running"
        ])
        
        return {
            "status": "healthy" if services_healthy else "degraded",
            "services": {
                "vision_ai": vision_models.get("total_models", 0) > 0,
                "audio_ai": audio_models.get("total_models", 0) > 0,
                "cross_modal_ai": True,  # Service should be available if this endpoint is reached
                "workflow_engine": workflow_status.get("status") == "running",
                "business_intelligence": bi_status.get("status") == "running"
            },
            "timestamp": datetime.utcnow().isoformat()
        }
        
    except Exception as e:
        return {
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.utcnow().isoformat()
        }

# Include router in main app
def include_multimodal_router(app):
    """Include multi-modal router in FastAPI app"""
    app.include_router(router)
    return app

# Export router
__all__ = ["router", "include_multimodal_router"]