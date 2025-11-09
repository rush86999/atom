import logging
import os

# Import AI components
import sys
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

sys.path.append(os.path.join(os.path.dirname(__file__), "..", "ai"))

from ai.automation_engine import AutomationEngine, AutomationWorkflow
from ai.data_intelligence import DataIntelligenceEngine, EntityType, PlatformType
from ai.nlp_engine import CommandIntent, NaturalLanguageEngine

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/ai", tags=["ai"])

# Initialize AI components
nlp_engine = NaturalLanguageEngine()
data_engine = DataIntelligenceEngine()
automation_engine = AutomationEngine()


# Pydantic Models
class NLPCommandRequest(BaseModel):
    command: str = Field(..., description="Natural language command")
    user_id: str = Field(..., description="User ID for context")


class NLPCommandResponse(BaseModel):
    success: bool = Field(..., description="Whether command was understood")
    confidence: float = Field(..., description="Confidence score (0.0-1.0)")
    command_type: str = Field(..., description="Type of command detected")
    platforms: List[str] = Field(..., description="Relevant platforms")
    entities: List[str] = Field(..., description="Detected entities")
    parameters: Dict[str, Any] = Field(..., description="Extracted parameters")
    message: str = Field(..., description="Human-readable response")
    suggested_actions: List[str] = Field(..., description="Suggested next actions")


class DataIngestRequest(BaseModel):
    platform: str = Field(..., description="Platform to ingest data from")
    data: List[Dict[str, Any]] = Field(..., description="Platform data to ingest")


class DataIngestResponse(BaseModel):
    success: bool = Field(..., description="Whether ingestion was successful")
    entities_created: int = Field(..., description="Number of entities created")
    entities_updated: int = Field(..., description="Number of entities updated")
    relationships_created: int = Field(
        ..., description="Number of relationships created"
    )


class DataSearchRequest(BaseModel):
    query: str = Field(..., description="Search query")
    entity_types: Optional[List[str]] = Field(
        None, description="Filter by entity types"
    )


class DataSearchResponse(BaseModel):
    results: List[Dict[str, Any]] = Field(..., description="Search results")
    total_count: int = Field(..., description="Total results found")


class WorkflowCreateRequest(BaseModel):
    name: str = Field(..., description="Workflow name")
    description: str = Field(..., description="Workflow description")
    trigger: Dict[str, Any] = Field(..., description="Trigger configuration")
    actions: List[Dict[str, Any]] = Field(..., description="List of actions")
    conditions: Optional[List[Dict[str, Any]]] = Field(
        [], description="Execution conditions"
    )


class WorkflowExecuteRequest(BaseModel):
    workflow_id: str = Field(..., description="Workflow ID to execute")
    trigger_data: Dict[str, Any] = Field(..., description="Trigger data")


class WorkflowExecuteResponse(BaseModel):
    execution_id: str = Field(..., description="Execution ID")
    status: str = Field(..., description="Execution status")
    actions_executed: List[str] = Field(..., description="Actions executed")
    errors: List[str] = Field(..., description="Any errors encountered")
    results: Dict[str, Any] = Field(..., description="Execution results")


class AIHealthResponse(BaseModel):
    status: str = Field(..., description="Overall AI system status")
    components: Dict[str, str] = Field(..., description="Individual component status")
    metrics: Dict[str, Any] = Field(..., description="System metrics")


# API Routes
@router.post("/nlp/parse")
async def parse_natural_language_command(
    request: NLPCommandRequest,
) -> NLPCommandResponse:
    """
    Parse natural language command and extract intent
    """
    try:
        logger.info(
            f"Parsing NLP command from user {request.user_id}: {request.command}"
        )

        # Parse the command
        intent = nlp_engine.parse_command(request.command)
        response_data = nlp_engine.generate_response(intent)

        return NLPCommandResponse(
            success=response_data["success"],
            confidence=response_data["confidence"],
            command_type=response_data["command_type"],
            platforms=response_data["platforms"],
            entities=response_data["entities"],
            parameters=response_data["parameters"],
            message=response_data["message"],
            suggested_actions=response_data["suggested_actions"],
        )

    except Exception as e:
        logger.error(f"NLP parsing failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"NLP parsing failed: {str(e)}")


@router.post("/data/ingest")
async def ingest_platform_data(request: DataIngestRequest) -> DataIngestResponse:
    """
    Ingest data from a specific platform into the unified data intelligence layer
    """
    try:
        logger.info(f"Ingesting data from platform: {request.platform}")

        # Convert platform string to enum
        try:
            platform_enum = PlatformType(request.platform.lower())
        except ValueError:
            raise HTTPException(
                status_code=400, detail=f"Unsupported platform: {request.platform}"
            )

        # Ingest the data
        unified_entities = data_engine.ingest_platform_data(platform_enum, request.data)

        # Calculate statistics
        entities_created = len(unified_entities)
        entities_updated = len(
            [e for e in unified_entities if len(e.source_platforms) > 1]
        )
        relationships_created = len(data_engine.relationship_registry)

        return DataIngestResponse(
            success=True,
            entities_created=entities_created,
            entities_updated=entities_updated,
            relationships_created=relationships_created,
        )

    except Exception as e:
        logger.error(f"Data ingestion failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Data ingestion failed: {str(e)}")


@router.post("/data/search")
async def search_unified_data(request: DataSearchRequest) -> DataSearchResponse:
    """
    Search across unified data from all platforms
    """
    try:
        logger.info(f"Searching unified data: {request.query}")

        # Convert entity types to enum if provided
        entity_types = None
        if request.entity_types:
            try:
                entity_types = [EntityType(et.lower()) for et in request.entity_types]
            except ValueError as e:
                raise HTTPException(
                    status_code=400, detail=f"Invalid entity type: {str(e)}"
                )

        # Perform search
        results = data_engine.search_unified_entities(request.query, entity_types)

        # Convert entities to serializable format
        serializable_results = []
        for entity in results:
            serializable_results.append(
                {
                    "entity_id": entity.entity_id,
                    "entity_type": entity.entity_type.value,
                    "canonical_name": entity.canonical_name,
                    "platforms": [p.value for p in entity.source_platforms],
                    "attributes": entity.attributes,
                    "confidence_score": entity.confidence_score,
                }
            )

        return DataSearchResponse(
            results=serializable_results, total_count=len(serializable_results)
        )

    except Exception as e:
        logger.error(f"Data search failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Data search failed: {str(e)}")


@router.get("/data/entities/{entity_id}")
async def get_entity_details(entity_id: str):
    """
    Get detailed information about a specific entity
    """
    try:
        entity = data_engine.entity_registry.get(entity_id)
        if not entity:
            raise HTTPException(status_code=404, detail=f"Entity {entity_id} not found")

        # Get relationships
        relationships = data_engine.get_entity_relationships(entity_id)

        # Get timeline
        timeline = data_engine.get_entity_timeline(entity_id)

        return {
            "entity": {
                "entity_id": entity.entity_id,
                "entity_type": entity.entity_type.value,
                "canonical_name": entity.canonical_name,
                "platform_mappings": {
                    p.value: pid for p, pid in entity.platform_mappings.items()
                },
                "attributes": entity.attributes,
                "relationships": entity.relationships,
                "confidence_score": entity.confidence_score,
                "source_platforms": [p.value for p in entity.source_platforms],
                "created_at": entity.created_at.isoformat(),
                "updated_at": entity.updated_at.isoformat(),
            },
            "relationships": [
                {
                    "relationship_id": rel.relationship_id,
                    "relationship_type": rel.relationship_type,
                    "target_entity_id": rel.target_entity_id,
                    "strength": rel.strength,
                    "created_at": rel.created_at.isoformat(),
                }
                for rel in relationships
            ],
            "timeline": timeline,
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to get entity details: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get entity details: {str(e)}"
        )


@router.post("/automation/workflows")
async def create_automation_workflow(request: WorkflowCreateRequest) -> Dict[str, Any]:
    """
    Create a new automation workflow
    """
    try:
        logger.info(f"Creating automation workflow: {request.name}")

        workflow_data = {
            "name": request.name,
            "description": request.description,
            "trigger": request.trigger,
            "actions": request.actions,
            "conditions": request.conditions,
        }

        workflow = automation_engine.create_workflow(workflow_data)

        return {
            "workflow_id": workflow.workflow_id,
            "name": workflow.name,
            "description": workflow.description,
            "trigger": {
                "trigger_id": workflow.trigger.trigger_id,
                "type": workflow.trigger.trigger_type.value,
                "platform": workflow.trigger.platform.value,
                "event_name": workflow.trigger.event_name,
            },
            "actions": [
                {
                    "action_id": action.action_id,
                    "type": action.action_type.value,
                    "platform": action.platform.value,
                    "description": action.description,
                }
                for action in workflow.actions
            ],
            "is_active": workflow.is_active,
            "created_at": workflow.created_at.isoformat(),
        }

    except Exception as e:
        logger.error(f"Workflow creation failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Workflow creation failed: {str(e)}"
        )


@router.post("/automation/workflows/{workflow_id}/execute")
async def execute_automation_workflow(
    workflow_id: str, request: WorkflowExecuteRequest
) -> WorkflowExecuteResponse:
    """
    Execute an automation workflow
    """
    try:
        logger.info(f"Executing workflow: {workflow_id}")

        import asyncio

        execution = await automation_engine.execute_workflow(
            workflow_id, request.trigger_data
        )

        return WorkflowExecuteResponse(
            execution_id=execution.execution_id,
            status=execution.status,
            actions_executed=execution.actions_executed,
            errors=execution.errors,
            results=execution.results,
        )

    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        logger.error(f"Workflow execution failed: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Workflow execution failed: {str(e)}"
        )


@router.get("/automation/workflows")
async def list_automation_workflows(active_only: bool = True) -> List[Dict[str, Any]]:
    """
    List all automation workflows
    """
    try:
        workflows = automation_engine.list_workflows(active_only)

        return [
            {
                "workflow_id": workflow.workflow_id,
                "name": workflow.name,
                "description": workflow.description,
                "trigger": {
                    "type": workflow.trigger.trigger_type.value,
                    "platform": workflow.trigger.platform.value,
                    "event_name": workflow.trigger.event_name,
                },
                "action_count": len(workflow.actions),
                "is_active": workflow.is_active,
                "created_at": workflow.created_at.isoformat(),
                "updated_at": workflow.updated_at.isoformat()
                if workflow.updated_at
                else None,
            }
            for workflow in workflows
        ]

    except Exception as e:
        logger.error(f"Failed to list workflows: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to list workflows: {str(e)}"
        )


@router.get("/automation/workflows/{workflow_id}/executions")
async def get_workflow_execution_history(
    workflow_id: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """
    Get execution history for a workflow
    """
    try:
        executions = automation_engine.get_execution_history(workflow_id, limit)

        return [
            {
                "execution_id": execution.execution_id,
                "status": execution.status,
                "start_time": execution.start_time.isoformat(),
                "end_time": execution.end_time.isoformat()
                if execution.end_time
                else None,
                "actions_executed_count": len(execution.actions_executed),
                "error_count": len(execution.errors),
            }
            for execution in executions
        ]

    except Exception as e:
        logger.error(f"Failed to get execution history: {str(e)}")
        raise HTTPException(
            status_code=500, detail=f"Failed to get execution history: {str(e)}"
        )


@router.get("/health")
async def ai_health_check() -> AIHealthResponse:
    """
    Health check for AI components
    """
    try:
        # Check NLP engine
        test_command = "test health check"
        nlp_intent = nlp_engine.parse_command(test_command)
        nlp_status = "healthy" if nlp_intent.confidence >= 0 else "degraded"

        # Check data engine
        data_status = "healthy" if len(data_engine.entity_registry) >= 0 else "degraded"

        # Check automation engine
        automation_status = (
            "healthy" if len(automation_engine.workflows) >= 0 else "degraded"
        )

        metrics = {
            "nlp_commands_processed": 0,  # Would track in production
            "unified_entities": len(data_engine.entity_registry),
            "data_relationships": len(data_engine.relationship_registry),
            "active_workflows": len(
                [w for w in automation_engine.workflows.values() if w.is_active]
            ),
            "total_executions": len(automation_engine.executions),
        }

        return AIHealthResponse(
            status="healthy"
            if all(
                [
                    nlp_status == "healthy",
                    data_status == "healthy",
                    automation_status == "healthy",
                ]
            )
            else "degraded",
            components={
                "nlp_engine": nlp_status,
                "data_intelligence": data_status,
                "automation_engine": automation_status,
            },
            metrics=metrics,
        )

    except Exception as e:
        logger.error(f"AI health check failed: {str(e)}")
        return AIHealthResponse(
            status="unhealthy",
            components={
                "nlp_engine": "unhealthy",
                "data_intelligence": "unhealthy",
                "automation_engine": "unhealthy",
            },
            metrics={},
        )


@router.get("/")
async def ai_root():
    """
    AI integration root endpoint
    """
    return {
        "service": "ai_integration",
        "status": "active",
        "version": "1.0.0",
        "description": "AI-Powered Intelligence and Automation Engine",
        "endpoints": {
            "nlp": {
                "/ai/nlp/parse": "Parse natural language commands",
            },
            "data": {
                "/ai/data/ingest": "Ingest platform data",
                "/ai/data/search": "Search unified data",
                "/ai/data/entities/{id}": "Get entity details",
            },
            "automation": {
                "/ai/automation/workflows": "Manage automation workflows",
                "/ai/automation/workflows/{id}/execute": "Execute workflows",
                "/ai/automation/workflows/{id}/executions": "Get execution history",
            },
            "system": {"/ai/health": "Health check", "/ai/": "This endpoint"},
        },
    }
