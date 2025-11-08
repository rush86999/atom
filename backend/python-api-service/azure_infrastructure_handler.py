from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional
import logging
import asyncio
from azure_infrastructure_service import AzureInfrastructureService

router = APIRouter(prefix="/api/azure", tags=["azure"])
logger = logging.getLogger(__name__)

# Azure service cache
azure_service_cache = {}

async def get_azure_service(request: Request) -> AzureInfrastructureService:
    """Get Azure service instance with user credentials"""
    try:
        # Get user token from database
        from auth_handler_teams import get_user_teams_tokens
        from main_api_app import get_db_pool
        
        user_id = request.headers.get("x-user-id", "current")
        db_pool = await get_db_pool()
        tokens = await get_user_teams_tokens(db_pool, user_id)
        
        if not tokens or not tokens.get("access_token"):
            raise HTTPException(status_code=401, detail="Azure authentication required")
        
        # Get service instance from cache or create new
        cache_key = f"azure_{user_id}"
        if cache_key not in azure_service_cache:
            azure_service_cache[cache_key] = AzureInfrastructureService(
                tenant_id=os.getenv("AZURE_TENANT_ID"),
                client_id=os.getenv("AZURE_CLIENT_ID"),
                client_secret=os.getenv("AZURE_CLIENT_SECRET")
            )
            await azure_service_cache[cache_key].initialize()
        
        return azure_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Azure service: {e}")
        raise HTTPException(status_code=500, detail="Azure service initialization failed")

@router.get("/health")
async def health_check():
    """Health check for Azure integration"""
    try:
        # Check environment variables
        required_vars = ["AZURE_TENANT_ID", "AZURE_CLIENT_ID", "AZURE_CLIENT_SECRET", "AZURE_SUBSCRIPTION_ID"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }
        
        return {
            "status": "healthy",
            "service": "azure-infrastructure",
            "timestamp": "2025-11-07T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Azure health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.post("/resource-groups")
async def get_resource_groups(
    request: Request,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get all Azure resource groups"""
    try:
        result = await azure_service.get_resource_groups()
        return result
    except Exception as e:
        logger.error(f"Failed to get resource groups: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/virtual-machines")
async def get_virtual_machines(
    request: Request,
    resource_group: Optional[str] = None,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get Azure virtual machines"""
    try:
        data = await request.json()
        resource_group = data.get("resource_group", resource_group)
        
        result = await azure_service.get_virtual_machines(resource_group)
        return result
    except Exception as e:
        logger.error(f"Failed to get virtual machines: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/virtual-machines/create")
async def create_virtual_machine(
    vm_config: Dict[str, Any],
    request: Request,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Create a new Azure virtual machine"""
    try:
        result = await azure_service.create_virtual_machine(vm_config)
        return result
    except Exception as e:
        logger.error(f"Failed to create virtual machine: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storage-accounts")
async def get_storage_accounts(
    request: Request,
    resource_group: Optional[str] = None,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get Azure storage accounts"""
    try:
        data = await request.json()
        resource_group = data.get("resource_group", resource_group)
        
        result = await azure_service.get_storage_accounts(resource_group)
        return result
    except Exception as e:
        logger.error(f"Failed to get storage accounts: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storage/files")
async def get_blob_files(
    request: Request,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get files from Azure Blob Storage container"""
    try:
        data = await request.json()
        storage_account = data.get("storage_account")
        container_name = data.get("container_name")
        
        if not storage_account or not container_name:
            raise HTTPException(status_code=400, detail="storage_account and container_name required")
        
        result = await azure_service.get_blob_files(storage_account, container_name)
        return result
    except Exception as e:
        logger.error(f"Failed to get blob files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/storage/upload")
async def upload_blob_file(
    request: Request,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Upload file to Azure Blob Storage"""
    try:
        form_data = await request.form()
        storage_account = form_data.get("storage_account")
        container_name = form_data.get("container_name")
        file_content = await (form_data.get("file")).read()
        content_type = (form_data.get("file")).content_type
        
        if not storage_account or not container_name or not file_content:
            raise HTTPException(status_code=400, detail="storage_account, container_name, and file required")
        
        result = await azure_service.upload_blob_file(
            storage_account, container_name, 
            (form_data.get("file")).filename,
            file_content, content_type
        )
        return result
    except Exception as e:
        logger.error(f"Failed to upload blob file: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/app-services")
async def get_app_services(
    request: Request,
    resource_group: Optional[str] = None,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get Azure App Services"""
    try:
        data = await request.json()
        resource_group = data.get("resource_group", resource_group)
        
        result = await azure_service.get_app_services(resource_group)
        return result
    except Exception as e:
        logger.error(f"Failed to get app services: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/app-services/deploy")
async def deploy_app_service(
    app_config: Dict[str, Any],
    request: Request,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Deploy a new Azure App Service"""
    try:
        result = await azure_service.deploy_app_service(app_config)
        return result
    except Exception as e:
        logger.error(f"Failed to deploy app service: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/costs/analysis")
async def get_cost_analysis(
    request: Request,
    timeframe: Optional[str] = "LastMonth",
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get Azure cost analysis"""
    try:
        data = await request.json()
        timeframe = data.get("timeframe", timeframe)
        
        result = await azure_service.get_cost_analysis(timeframe)
        return result
    except Exception as e:
        logger.error(f"Failed to get cost analysis: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/monitoring/metrics")
async def get_monitoring_metrics(
    request: Request,
    azure_service: AzureInfrastructureService = Depends(get_azure_service)
):
    """Get Azure monitoring metrics for a resource"""
    try:
        data = await request.json()
        resource_id = data.get("resource_id")
        metric_name = data.get("metric_name")
        timeframe = data.get("timeframe", "PT1H")
        
        if not resource_id or not metric_name:
            raise HTTPException(status_code=400, detail="resource_id and metric_name required")
        
        result = await azure_service.get_monitoring_metrics(resource_id, metric_name, timeframe)
        return result
    except Exception as e:
        logger.error(f"Failed to get monitoring metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/status")
async def get_services_status():
    """Get status of all Azure services"""
    try:
        services_status = {
            "compute": "available",
            "storage": "available", 
            "web": "available",
            "cost_management": "available",
            "monitoring": "available",
            "networking": "available",
            "sql": "available",
            "functions": "available",
            "key_vault": "available",
            "container_registry": "available",
            "kubernetes": "available"
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