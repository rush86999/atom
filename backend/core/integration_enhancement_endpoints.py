"""
Enhanced Integration Capabilities Endpoints
API endpoints for advanced data mapping, bulk operations, and integration analytics
"""

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Body, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from .bulk_operations_processor import BulkOperation, IntegrationBulkProcessor, get_bulk_processor
from .integration_data_mapper import (
    FieldMapping,
    FieldType,
    IntegrationDataMapper,
    IntegrationSchema,
    TransformationType,
    get_data_mapper,
)

router = APIRouter()

# Pydantic models for requests/responses

class FieldMappingRequest(BaseModel):
    source_field: str
    target_field: str
    source_type: str
    target_type: str
    transformation: str
    transformation_config: Optional[Dict[str, Any]] = None
    required: bool = True
    default_value: Optional[Any] = None

class CreateMappingRequest(BaseModel):
    mapping_id: str
    source_schema: str
    target_schema: str
    field_mappings: List[FieldMappingRequest]

class TransformDataRequest(BaseModel):
    data: List[Dict[str, Any]]
    mapping_id: str

class BulkOperationRequest(BaseModel):
    operation_type: str  # create, update, delete, upsert
    integration_id: str
    items: List[Dict[str, Any]]
    batch_size: int = 100
    parallel_processing: bool = True
    stop_on_error: bool = False
    mapping_id: Optional[str] = None
    schema_id: Optional[str] = None

class SchemaRegistrationRequest(BaseModel):
    integration_id: str
    integration_name: str
    version: str = "1.0"
    fields: Dict[str, Dict[str, Any]]
    supported_operations: List[str]
    bulk_operations_supported: bool = False
    max_bulk_size: Optional[int] = None

# Schema Management Endpoints

@router.get("/api/v1/integrations/schemas")
async def list_schemas(
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """List all registered integration schemas"""
    schemas = data_mapper.list_schemas()
    schema_details = {}

    for schema_id in schemas:
        schema = data_mapper.get_schema_info(schema_id)
        if schema:
            schema_details[schema_id] = {
                "integration_name": schema.integration_name,
                "version": schema.version,
                "field_count": len(schema.fields),
                "supported_operations": schema.supported_operations,
                "bulk_operations_supported": schema.bulk_operations_supported,
                "max_bulk_size": schema.max_bulk_size
            }

    return {
        "success": True,
        "schemas": schema_details,
        "total_schemas": len(schemas)
    }

@router.get("/api/v1/integrations/schemas/{schema_id}")
async def get_schema_details(
    schema_id: str,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Get detailed schema information"""
    schema = data_mapper.get_schema_info(schema_id)
    if not schema:
        raise HTTPException(status_code=404, detail=f"Schema {schema_id} not found")

    return {
        "success": True,
        "schema": {
            "integration_id": schema.integration_id,
            "integration_name": schema.integration_name,
            "version": schema.version,
            "fields": schema.fields,
            "supported_operations": schema.supported_operations,
            "bulk_operations_supported": schema.bulk_operations_supported,
            "max_bulk_size": schema.max_bulk_size
        }
    }

@router.post("/api/v1/integrations/schemas")
async def register_schema(
    request: SchemaRegistrationRequest,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Register a new integration schema"""
    try:
        schema = IntegrationSchema(
            integration_id=request.integration_id,
            integration_name=request.integration_name,
            version=request.version,
            fields=request.fields,
            supported_operations=request.supported_operations,
            bulk_operations_supported=request.bulk_operations_supported,
            max_bulk_size=request.max_bulk_size
        )

        data_mapper.register_schema(schema)

        return {
            "success": True,
            "message": f"Schema {request.integration_id} registered successfully",
            "schema_id": request.integration_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to register schema: {str(e)}"
        )

# Data Mapping Endpoints

@router.get("/api/v1/integrations/mappings")
async def list_mappings(
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """List all registered data mappings"""
    mappings = data_mapper.list_mappings()
    mapping_details = {}

    for mapping_id in mappings:
        try:
            exported = data_mapper.export_mapping(mapping_id)
            mapping_details[mapping_id] = {
                "field_count": len(exported["field_mappings"]),
                "exported_at": exported["exported_at"]
            }
        except Exception as e:
            mapping_details[mapping_id] = {"error": str(e)}

    return {
        "success": True,
        "mappings": mapping_details,
        "total_mappings": len(mappings)
    }

@router.post("/api/v1/integrations/mappings")
async def create_mapping(
    request: CreateMappingRequest,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Create a new data mapping between schemas"""
    try:
        # Convert request models to FieldMapping objects
        field_mappings = []
        for fm_request in request.field_mappings:
            field_mapping = FieldMapping(
                source_field=fm_request.source_field,
                target_field=fm_request.target_field,
                source_type=FieldType(fm_request.source_type),
                target_type=FieldType(fm_request.target_type),
                transformation=TransformationType(fm_request.transformation),
                transformation_config=fm_request.transformation_config,
                required=fm_request.required,
                default_value=fm_request.default_value
            )
            field_mappings.append(field_mapping)

        data_mapper.create_mapping(
            request.mapping_id,
            request.source_schema,
            request.target_schema,
            field_mappings
        )

        return {
            "success": True,
            "message": f"Mapping {request.mapping_id} created successfully",
            "mapping_id": request.mapping_id,
            "field_count": len(field_mappings)
        }
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to create mapping: {str(e)}"
        )

@router.get("/api/v1/integrations/mappings/{mapping_id}")
async def get_mapping_details(
    mapping_id: str,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Get detailed mapping information"""
    try:
        mapping_data = data_mapper.export_mapping(mapping_id)
        return {
            "success": True,
            "mapping": mapping_data
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/api/v1/integrations/mappings/{mapping_id}/transform")
async def transform_data(
    mapping_id: str,
    request: TransformDataRequest,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Transform data using a specific mapping"""
    try:
        # Validate mapping exists
        mappings = data_mapper.list_mappings()
        if mapping_id not in mappings:
            raise HTTPException(status_code=404, detail=f"Mapping {mapping_id} not found")

        # Transform data
        transformed_data = data_mapper.transform_data(request.data, mapping_id)

        return {
            "success": True,
            "transformed_data": transformed_data,
            "items_transformed": len(request.data)
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data transformation failed: {str(e)}"
        )

@router.post("/api/v1/integrations/validate")
async def validate_data(
    data: List[Dict[str, Any]],
    schema_id: str,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Validate data against a schema"""
    try:
        validation_result = data_mapper.validate_data(data, schema_id)
        return {
            "success": True,
            "validation": validation_result
        }
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Data validation failed: {str(e)}"
        )

# Bulk Operations Endpoints

@router.post("/api/v1/integrations/bulk")
async def submit_bulk_operation(
    request: BulkOperationRequest,
    bulk_processor: IntegrationBulkProcessor = Depends(get_bulk_processor)
):
    """Submit a bulk operation for processing"""
    try:
        operation = BulkOperation(
            operation_type=request.operation_type,
            integration_id=request.integration_id,
            items=request.items,
            batch_size=request.batch_size,
            parallel_processing=request.parallel_processing,
            stop_on_error=request.stop_on_error
        )

        # Add optional attributes
        if request.mapping_id:
            operation.mapping_id = request.mapping_id
        if request.schema_id:
            operation.schema_id = request.schema_id

        job_id = await bulk_processor.submit_bulk_job(operation)

        return {
            "success": True,
            "job_id": job_id,
            "message": f"Bulk operation submitted with {len(request.items)} items"
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to submit bulk operation: {str(e)}"
        )

@router.get("/api/v1/integrations/bulk/{job_id}")
async def get_bulk_job_status(
    job_id: str,
    bulk_processor: IntegrationBulkProcessor = Depends(get_bulk_processor)
):
    """Get status of a bulk operation job"""
    job = await bulk_processor.get_job_status(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    return {
        "success": True,
        "job": {
            "job_id": job.job_id,
            "status": job.status.value,
            "created_at": job.created_at.isoformat(),
            "started_at": job.started_at.isoformat() if job.started_at else None,
            "completed_at": job.completed_at.isoformat() if job.completed_at else None,
            "total_items": job.total_items,
            "processed_items": job.processed_items,
            "successful_items": job.successful_items,
            "failed_items": job.failed_items,
            "progress_percentage": job.progress_percentage,
            "estimated_completion": job.estimated_completion,
            "error_count": len(job.errors),
            "recent_errors": job.errors[-5:] if job.errors else []
        }
    }

@router.post("/api/v1/integrations/bulk/{job_id}/cancel")
async def cancel_bulk_job(
    job_id: str,
    bulk_processor: IntegrationBulkProcessor = Depends(get_bulk_processor)
):
    """Cancel a bulk operation job"""
    success = await bulk_processor.cancel_job(job_id)
    if not success:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found or cannot be cancelled")

    return {
        "success": True,
        "message": f"Job {job_id} cancelled successfully"
    }

@router.get("/api/v1/integrations/bulk/stats")
async def get_bulk_processing_stats(
    bulk_processor: IntegrationBulkProcessor = Depends(get_bulk_processor)
):
    """Get bulk processing performance statistics"""
    stats = bulk_processor.get_performance_stats()
    return {
        "success": True,
        "stats": stats
    }

# Integration Analytics Endpoints

@router.get("/api/v1/integrations/analytics")
async def get_integration_analytics(
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper),
    bulk_processor: IntegrationBulkProcessor = Depends(get_bulk_processor)
):
    """Get comprehensive integration analytics"""
    try:
        # Schema analytics
        schemas = data_mapper.list_schemas()
        schema_types = {}
        bulk_capable = 0

        for schema_id in schemas:
            schema = data_mapper.get_schema_info(schema_id)
            if schema:
                integration_type = schema.integration_name.split()[0].lower()
                schema_types[integration_type] = schema_types.get(integration_type, 0) + 1
                if schema.bulk_operations_supported:
                    bulk_capable += 1

        # Mapping analytics
        mappings = data_mapper.list_mappings()
        mapping_complexity = []
        for mapping_id in mappings:
            try:
                exported = data_mapper.export_mapping(mapping_id)
                mapping_complexity.append(len(exported["field_mappings"]))
            except Exception as e:
                logger.debug(f"Failed to export mapping {mapping_id}: {e}")

        # Bulk operations analytics
        bulk_stats = bulk_processor.get_performance_stats()

        analytics = {
            "schemas": {
                "total_count": len(schemas),
                "bulk_capable": bulk_capable,
                "by_type": schema_types
            },
            "mappings": {
                "total_count": len(mappings),
                "average_complexity": sum(mapping_complexity) / len(mapping_complexity) if mapping_complexity else 0,
                "max_complexity": max(mapping_complexity) if mapping_complexity else 0
            },
            "bulk_operations": bulk_stats,
            "generated_at": datetime.now(timezone.utc).isoformat()
        }

        return {
            "success": True,
            "analytics": analytics
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to generate analytics: {str(e)}"
        )

# Pre-built Mapping Templates

@router.get("/api/v1/integrations/mapping-templates")
async def get_mapping_templates(
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Get pre-built mapping templates for common integrations"""
    templates = {
        "asana_to_jira": {
            "source_schema": "asana_task",
            "target_schema": "jira_issue",
            "description": "Map Asana tasks to Jira issues",
            "field_mappings": [
                {
                    "source_field": "name",
                    "target_field": "summary",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": True
                },
                {
                    "source_field": "description",
                    "target_field": "description",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": False
                },
                {
                    "source_field": "completed",
                    "target_field": "status",
                    "source_type": "boolean",
                    "target_type": "string",
                    "transformation": "conditional",
                    "transformation_config": {
                        "conditions": [
                            {
                                "field": "self",
                                "operator": "equals",
                                "expected": True,
                                "result": "Done"
                            }
                        ],
                        "default": "To Do"
                    },
                    "required": False
                },
                {
                    "source_field": "assignee",
                    "target_field": "assignee",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": False
                }
            ]
        },
        "salesforce_to_hubspot": {
            "source_schema": "salesforce_lead",
            "target_schema": "hubspot_contact",
            "description": "Map Salesforce leads to HubSpot contacts",
            "field_mappings": [
                {
                    "source_field": "FirstName",
                    "target_field": "firstname",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": False
                },
                {
                    "source_field": "LastName",
                    "target_field": "lastname",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": True
                },
                {
                    "source_field": "Email",
                    "target_field": "email",
                    "source_type": "email",
                    "target_type": "email",
                    "transformation": "format_conversion",
                    "transformation_config": {
                        "format_type": "lowercase"
                    },
                    "required": False
                },
                {
                    "source_field": "Company",
                    "target_field": "company",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": False
                }
            ]
        }
    }

    return {
        "success": True,
        "templates": templates,
        "total_templates": len(templates)
    }

@router.post("/api/v1/integrations/mapping-templates/{template_name}")
async def apply_mapping_template(
    template_name: str,
    mapping_id: str,
    data_mapper: IntegrationDataMapper = Depends(get_data_mapper)
):
    """Apply a pre-built mapping template"""
    templates = {
        "asana_to_jira": {
            "source_schema": "asana_task",
            "target_schema": "jira_issue",
            "field_mappings": [
                {
                    "source_field": "name",
                    "target_field": "summary",
                    "source_type": "string",
                    "target_type": "string",
                    "transformation": "direct_copy",
                    "required": True
                }
                # ... more mappings would be defined here
            ]
        }
        # ... more templates
    }

    if template_name not in templates:
        raise HTTPException(status_code=404, detail=f"Template {template_name} not found")

    template = templates[template_name]

    try:
        # Convert template to FieldMapping objects
        field_mappings = []
        for fm_data in template["field_mappings"]:
            field_mapping = FieldMapping(
                source_field=fm_data["source_field"],
                target_field=fm_data["target_field"],
                source_type=FieldType(fm_data["source_type"]),
                target_type=FieldType(fm_data["target_type"]),
                transformation=TransformationType(fm_data["transformation"]),
                transformation_config=fm_data.get("transformation_config"),
                required=fm_data.get("required", True),
                default_value=fm_data.get("default_value")
            )
            field_mappings.append(field_mapping)

        data_mapper.create_mapping(
            mapping_id,
            template["source_schema"],
            template["target_schema"],
            field_mappings
        )

        return {
            "success": True,
            "message": f"Template {template_name} applied as mapping {mapping_id}",
            "mapping_id": mapping_id
        }
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to apply template: {str(e)}"
        )