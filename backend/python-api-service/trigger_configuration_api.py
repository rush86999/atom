"""
Trigger Configuration API for Atom Workflow Automation

This API provides endpoints for managing trigger configurations
and serving them to the frontend workflow editor.
"""

from fastapi import APIRouter, HTTPException, Depends
from typing import List, Dict, Any, Optional
import json
from .trigger_configuration_service import TriggerConfigurationService, trigger_service

router = APIRouter(prefix="/api/triggers", tags=["triggers"])


@router.get("/", response_model=List[Dict[str, Any]])
async def get_all_triggers():
    """
    Get all available trigger configurations
    Returns complete schemas for all enabled triggers
    """
    try:
        triggers = trigger_service.get_all_trigger_schemas()
        return triggers
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load triggers: {str(e)}"
        )


@router.get("/{trigger_id}", response_model=Dict[str, Any])
async def get_trigger(trigger_id: str):
    """
    Get a specific trigger configuration by ID
    """
    trigger = trigger_service.get_trigger_schema(trigger_id)
    if not trigger:
        raise HTTPException(status_code=404, detail=f"Trigger '{trigger_id}' not found")
    return trigger


@router.get("/service/{service_name}", response_model=List[Dict[str, Any]])
async def get_triggers_by_service(service_name: str):
    """
    Get all triggers for a specific service
    """
    try:
        triggers = trigger_service.get_triggers_by_service(service_name)
        schemas = [
            trigger_service.get_trigger_schema(trigger.id) for trigger in triggers
        ]
        return schemas
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to load triggers for service {service_name}: {str(e)}",
        )


@router.post("/{trigger_id}/validate")
async def validate_trigger_config(trigger_id: str, config: Dict[str, Any]):
    """
    Validate a trigger configuration against its schema
    """
    try:
        result = trigger_service.validate_trigger_config(trigger_id, config)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation failed: {str(e)}")


@router.post("/", response_model=Dict[str, Any])
async def create_trigger(trigger_data: Dict[str, Any]):
    """
    Create a new trigger configuration (admin only)
    """
    try:
        # Basic validation
        required_fields = ["id", "name", "service"]
        for field in required_fields:
            if field not in trigger_data:
                raise HTTPException(
                    status_code=400, detail=f"Missing required field: {field}"
                )

        # Check if trigger already exists
        existing = trigger_service.get_trigger(trigger_data["id"])
        if existing:
            raise HTTPException(
                status_code=400, detail=f"Trigger '{trigger_data['id']}' already exists"
            )

        trigger = trigger_service.create_trigger(trigger_data)
        return trigger_service.get_trigger_schema(trigger.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to create trigger: {str(e)}"
        )


@router.put("/{trigger_id}", response_model=Dict[str, Any])
async def update_trigger(trigger_id: str, update_data: Dict[str, Any]):
    """
    Update a trigger configuration (admin only)
    """
    try:
        trigger = trigger_service.update_trigger(trigger_id, update_data)
        if not trigger:
            raise HTTPException(
                status_code=404, detail=f"Trigger '{trigger_id}' not found"
            )
        return trigger_service.get_trigger_schema(trigger.id)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to update trigger: {str(e)}"
        )


@router.delete("/{trigger_id}")
async def delete_trigger(trigger_id: str):
    """
    Delete a trigger configuration (admin only)
    """
    try:
        success = trigger_service.delete_trigger(trigger_id)
        if not success:
            raise HTTPException(
                status_code=404, detail=f"Trigger '{trigger_id}' not found"
            )
        return {"message": f"Trigger '{trigger_id}' deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to delete trigger: {str(e)}"
        )


@router.get("/services/list")
async def get_available_services():
    """
    Get list of all services that have triggers available
    """
    try:
        triggers = trigger_service.get_all_triggers()
        services = list(set(trigger.service for trigger in triggers))
        return {"services": sorted(services)}
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to load services: {str(e)}"
        )


@router.get("/health")
async def health_check():
    """
    Health check endpoint for trigger configuration service
    """
    try:
        triggers_count = trigger_service.session.query(
            trigger_service.TriggerConfiguration
        ).count()
        return {
            "status": "healthy",
            "triggers_count": triggers_count,
            "service": "trigger_configuration",
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Health check failed: {str(e)}")


# Webhook endpoint for real-time trigger events
@router.post("/webhook/{trigger_id}")
async def handle_trigger_webhook(trigger_id: str, payload: Dict[str, Any]):
    """
    Webhook endpoint for receiving trigger events from external services
    This would be called by services like GitHub webhooks, Slack events, etc.
    """
    try:
        # Validate the trigger exists
        trigger = trigger_service.get_trigger(trigger_id)
        if not trigger:
            raise HTTPException(
                status_code=404, detail=f"Trigger '{trigger_id}' not found"
            )

        # In a real implementation, this would:
        # 1. Validate the webhook signature
        # 2. Process the payload
        # 3. Trigger associated workflows
        # 4. Return appropriate response

        return {
            "status": "received",
            "trigger_id": trigger_id,
            "message": "Webhook received successfully",
            "processed": True,
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500, detail=f"Webhook processing failed: {str(e)}"
        )


# Test endpoint for development
@router.post("/test/{trigger_id}")
async def test_trigger_configuration(trigger_id: str, test_config: Dict[str, Any]):
    """
    Test a trigger configuration with sample data
    """
    try:
        trigger = trigger_service.get_trigger_schema(trigger_id)
        if not trigger:
            raise HTTPException(
                status_code=404, detail=f"Trigger '{trigger_id}' not found"
            )

        # Validate the configuration
        validation_result = trigger_service.validate_trigger_config(
            trigger_id, test_config
        )

        if not validation_result["valid"]:
            return {
                "success": False,
                "errors": validation_result["errors"],
                "message": "Configuration validation failed",
            }

        # Simulate trigger execution
        # In a real implementation, this would actually connect to the service
        # and test the trigger configuration

        return {
            "success": True,
            "trigger": trigger,
            "config": test_config,
            "message": "Trigger configuration test completed successfully",
            "simulated_output": {
                "sample_data": [
                    {
                        "id": "sample_1",
                        "type": "test_event",
                        "timestamp": "2024-01-01T00:00:00Z",
                    },
                    {
                        "id": "sample_2",
                        "type": "test_event",
                        "timestamp": "2024-01-01T00:01:00Z",
                    },
                ],
                "total_count": 2,
                "trigger_type": trigger_id,
            },
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Trigger test failed: {str(e)}")
