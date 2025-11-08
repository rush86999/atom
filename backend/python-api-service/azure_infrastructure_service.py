import os
import json
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional, List
import asyncio
import httpx
from azure.identity import DefaultAzureCredential
from azure.mgmt.resource import ResourceManagementClient
from azure.mgmt.compute import ComputeManagementClient
from azure.mgmt.storage import StorageManagementClient
from azure.mgmt.web import WebSiteManagementClient
from azure.mgmt.costmanagement import CostManagementClient
from azure.mgmt.monitor import MonitorManagementClient
from azure.storage.blob import BlobServiceClient
from azure.core.exceptions import AzureError

logger = logging.getLogger(__name__)

class AzureInfrastructureService:
    """Comprehensive Azure Infrastructure Management Service"""
    
    def __init__(self, tenant_id: str, client_id: str, client_secret: str):
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.credential = None
        self.subscription_id = os.getenv("AZURE_SUBSCRIPTION_ID")
        
        # Initialize clients
        self.resource_client = None
        self.compute_client = None
        self.storage_client = None
        self.web_client = None
        self.cost_client = None
        self.monitor_client = None
        
    async def initialize(self):
        """Initialize Azure clients with credentials"""
        try:
            from azure.identity import ClientSecretCredential
            self.credential = ClientSecretCredential(
                tenant_id=self.tenant_id,
                client_id=self.client_id,
                client_secret=self.client_secret
            )
            
            # Initialize management clients
            self.resource_client = ResourceManagementClient(
                credential=self.credential, 
                subscription_id=self.subscription_id
            )
            self.compute_client = ComputeManagementClient(
                credential=self.credential, 
                subscription_id=self.subscription_id
            )
            self.storage_client = StorageManagementClient(
                credential=self.credential, 
                subscription_id=self.subscription_id
            )
            self.web_client = WebSiteManagementClient(
                credential=self.credential, 
                subscription_id=self.subscription_id
            )
            self.cost_client = CostManagementClient(
                credential=self.credential
            )
            self.monitor_client = MonitorManagementClient(
                credential=self.credential,
                subscription_id=self.subscription_id
            )
            
            logger.info("Azure clients initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to initialize Azure clients: {e}")
            return False
    
    async def get_resource_groups(self) -> Dict[str, Any]:
        """Get all resource groups"""
        try:
            resource_groups = []
            async for rg in self.resource_client.resource_groups.list():
                resource_groups.append({
                    "id": str(rg.id),
                    "name": rg.name,
                    "location": rg.location,
                    "tags": rg.tags,
                    "properties": rg.properties,
                    "created_at": rg.tags.get("created_at", "") if rg.tags else ""
                })
            
            return {
                "success": True,
                "data": resource_groups
            }
            
        except Exception as e:
            logger.error(f"Failed to get resource groups: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_virtual_machines(self, resource_group: str = None) -> Dict[str, Any]:
        """Get all virtual machines or VMs in specific resource group"""
        try:
            vms = []
            if resource_group:
                vm_list = self.compute_client.virtual_machines.list(resource_group)
            else:
                vm_list = self.compute_client.virtual_machines.list_all()
            
            async for vm in vm_list:
                # Get VM status
                instance_view = self.compute_client.virtual_machines.instance_view(
                    vm.id.split('/')[4],  # resource group
                    vm.name
                )
                
                status = "Unknown"
                for status_info in instance_view.statuses:
                    if status_info.code.startswith("PowerState/"):
                        status = status_info.code.split("/")[-1].title()
                        break
                
                vms.append({
                    "id": str(vm.id),
                    "name": vm.name,
                    "location": vm.location,
                    "size": vm.hardware_profile.vm_size,
                    "status": status,
                    "os_type": vm.storage_profile.os_disk.os_type.value if vm.storage_profile.os_disk.os_type else "Unknown",
                    "admin_username": vm.os_profile.admin_username if vm.os_profile.admin_username else None,
                    "public_ip": None,  # Will be populated separately
                    "created_at": None,  # Will be populated from tags
                    "resource_group": vm.id.split('/')[4]
                })
            
            return {
                "success": True,
                "data": vms
            }
            
        except Exception as e:
            logger.error(f"Failed to get virtual machines: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_storage_accounts(self, resource_group: str = None) -> Dict[str, Any]:
        """Get all storage accounts or storage accounts in specific resource group"""
        try:
            storage_accounts = []
            if resource_group:
                storage_list = self.storage_client.storage_accounts.list_by_resource_group(resource_group)
            else:
                storage_list = self.storage_client.storage_accounts.list()
            
            async for storage in storage_list:
                # Get account usage
                usage = self.storage_client.storage_accounts.get_usage(storage.name, storage.location)
                
                storage_accounts.append({
                    "id": str(storage.id),
                    "name": storage.name,
                    "location": storage.location,
                    "type": storage.kind.value if storage.kind else "Unknown",
                    "tier": storage.sku.tier.value if storage.sku and storage.sku.tier else "Unknown",
                    "replication": storage.sku.name.value if storage.sku and storage.sku.name else "Unknown",
                    "access_tier": storage.access_tier.value if storage.access_tier else "Unknown",
                    "blob_endpoint": storage.primary_endpoints.blob if storage.primary_endpoints else None,
                    "file_endpoint": storage.primary_endpoints.file if storage.primary_endpoints else None,
                    "created_at": storage.creation_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if storage.creation_time else None,
                    "resource_group": storage.id.split('/')[4]
                })
            
            return {
                "success": True,
                "data": storage_accounts
            }
            
        except Exception as e:
            logger.error(f"Failed to get storage accounts: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_app_services(self, resource_group: str = None) -> Dict[str, Any]:
        """Get all app services or app services in specific resource group"""
        try:
            app_services = []
            if resource_group:
                apps_list = self.web_client.web_apps.list_by_resource_group(resource_group)
            else:
                apps_list = self.web_client.web_apps.list()
            
            async for app in apps_list:
                app_services.append({
                    "id": str(app.id),
                    "name": app.name,
                    "location": app.location,
                    "state": app.state if app.state else "Unknown",
                    "host_names": app.host_names,
                    "app_service_plan": app.app_service_plan_id.split('/')[-1] if app.app_service_plan_id else None,
                    "runtime": app.site_config.java_version if app.site_config and app.site_config.java_version else "Unknown",
                    "https_only": app.site_config.https_only if app.site_config else False,
                    "created_at": None,  # Will be populated from tags
                    "resource_group": app.id.split('/')[4]
                })
            
            return {
                "success": True,
                "data": app_services
            }
            
        except Exception as e:
            logger.error(f"Failed to get app services: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def create_virtual_machine(self, vm_config: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new virtual machine"""
        try:
            from azure.mgmt.compute.models import (
                VirtualMachine, HardwareProfile, VMSize, StorageProfile,
                OSDisk, CreateOption, ImageReference, OSProfile,
                NetworkReference, NetworkInterfaceReference
            )
            
            resource_group = vm_config["resource_group"]
            vm_name = vm_config["vm_name"]
            
            # Create VM configuration
            vm_parameters = VirtualMachine(
                location=vm_config["location"],
                hardware_profile=HardwareProfile(
                    vm_size=vm_config["size"]
                ),
                storage_profile=StorageProfile(
                    os_disk=OSDisk(
                        create_option=CreateOption.from_image,
                        name=f"{vm_name}-os-disk",
                        managed_disk=None  # Will be auto-managed
                    ),
                    image_reference=ImageReference(
                        publisher=vm_config["image_publisher"],
                        offer=vm_config["image_offer"],
                        sku=vm_config["image_sku"],
                        version="latest"
                    )
                ),
                os_profile=OSProfile(
                    admin_username=vm_config["admin_username"],
                    admin_password=vm_config["admin_password"],
                    computer_name=vm_name
                ),
                network_profile=NetworkProfile(
                    network_interfaces=[
                        NetworkInterfaceReference(
                            id=vm_config["network_interface_id"]
                        )
                    ]
                )
            )
            
            # Create VM
            poller = self.compute_client.virtual_machines.begin_create_or_update(
                resource_group,
                vm_name,
                vm_parameters
            )
            
            vm_result = await poller.result()
            
            return {
                "success": True,
                "data": {
                    "id": str(vm_result.id),
                    "name": vm_result.name,
                    "status": "Creating"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to create virtual machine: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_blob_files(self, storage_account: str, container_name: str) -> Dict[str, Any]:
        """Get files from Azure Blob Storage container"""
        try:
            # Get storage account key
            storage_keys = self.storage_client.storage_accounts.list_keys(
                storage_account.split('/')[4],  # resource group
                storage_account
            )
            key = next(key for key in storage_keys.keys if key.key_name == "key1").value
            
            # Create blob service client
            blob_service = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=key
            )
            
            # List files in container
            container_client = blob_service.get_container_client(container_name)
            files = []
            
            async for blob in container_client.list_blobs():
                # Get file properties
                blob_client = container_client.get_blob_client(blob.name)
                properties = await blob_client.get_blob_properties()
                
                files.append({
                    "name": blob.name,
                    "size": properties.size,
                    "content_type": properties.content_settings.content_type if properties.content_settings else None,
                    "last_modified": properties.last_modified.strftime("%Y-%m-%dT%H:%M:%S.%fZ") if properties.last_modified else None,
                    "etag": properties.etag
                })
            
            return {
                "success": True,
                "data": files
            }
            
        except Exception as e:
            logger.error(f"Failed to get blob files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def upload_blob_file(self, storage_account: str, container_name: str, 
                             file_path: str, file_content: bytes, content_type: str) -> Dict[str, Any]:
        """Upload file to Azure Blob Storage"""
        try:
            # Get storage account key
            storage_keys = self.storage_client.storage_accounts.list_keys(
                storage_account.split('/')[4],  # resource group
                storage_account
            )
            key = next(key for key in storage_keys.keys if key.key_name == "key1").value
            
            # Create blob service client
            blob_service = BlobServiceClient(
                account_url=f"https://{storage_account}.blob.core.windows.net",
                credential=key
            )
            
            # Upload file
            blob_client = blob_service.get_blob_client(container_name, file_path)
            await blob_client.upload_blob(
                file_content,
                overwrite=True,
                content_settings={'content_type': content_type}
            )
            
            return {
                "success": True,
                "data": {
                    "file_path": file_path,
                    "size": len(file_content),
                    "uploaded_at": datetime.now(timezone.utc).isoformat()
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to upload blob file: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_cost_analysis(self, timeframe: str = "LastMonth") -> Dict[str, Any]:
        """Get Azure cost analysis"""
        try:
            from azure.mgmt.costmanagement.models import QueryTimeperiod, TimeframeType, QueryDefinition, QueryAggregation, QueryGrouping, QueryColumn, QueryComparisonExpression, QueryFilter
            
            # Query parameters
            query_definition = QueryDefinition(
                type="ActualCost",
                timeperiod=QueryTimeperiod(
                    from_property=datetime.now(timezone.utc).replace(day=1).isoformat(),
                    to_property=datetime.now(timezone.utc).isoformat()
                ),
                dataset={
                    "granularity": "Daily",
                    "aggregation": {
                        "totalCost": QueryAggregation(name="Cost", function="Sum")
                    },
                    "grouping": [
                        QueryGrouping(type="Dimension", name="ServiceName"),
                        QueryGrouping(type="Dimension", name="ResourceGroup")
                    ]
                }
            )
            
            # Execute query
            result = self.cost_client.query.usage(
                scope=f"/subscriptions/{self.subscription_id}",
                query_definition=query_definition
            )
            
            costs = []
            for row in result.rows:
                costs.append({
                    "date": row[0],
                    "service_name": row[1],
                    "resource_group": row[2],
                    "currency": row[3],
                    "cost": row[4]
                })
            
            return {
                "success": True,
                "data": {
                    "costs": costs,
                    "total_cost": sum(row[4] for row in result.rows),
                    "currency": result.rows[0][3] if result.rows else "USD"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get cost analysis: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_monitoring_metrics(self, resource_id: str, metric_name: str, 
                                  timeframe: str = "PT1H") -> Dict[str, Any]:
        """Get Azure monitoring metrics for a resource"""
        try:
            # Get metrics
            metrics_data = self.monitor_client.metrics.list(
                resource_uri=resource_id,
                metricnames=metric_name,
                timespan=timeframe,
                aggregation="Average"
            )
            
            metrics = []
            async for metric in metrics_data:
                for time_series in metric.timeseries:
                    for data_point in time_series.data:
                        metrics.append({
                            "timestamp": data_point.time_stamp.isoformat() if data_point.time_stamp else None,
                            "value": data_point.average if data_point.average else 0,
                            "unit": metric.unit.name if metric.unit else "Unknown"
                        })
            
            return {
                "success": True,
                "data": metrics
            }
            
        except Exception as e:
            logger.error(f"Failed to get monitoring metrics: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def deploy_app_service(self, app_config: Dict[str, Any]) -> Dict[str, Any]:
        """Deploy a new Azure App Service"""
        try:
            from azure.mgmt.web.models import (
                Site, SiteConfig, AppServicePlan, SkuDescription
            )
            
            resource_group = app_config["resource_group"]
            app_name = app_config["app_name"]
            
            # Create app service plan if needed
            plan_name = app_config.get("plan_name", f"{app_name}-plan")
            plan_sku = SkuDescription(
                tier=app_config.get("plan_tier", "Basic"),
                name=app_config.get("plan_size", "B1")
            )
            
            plan = AppServicePlan(
                location=app_config["location"],
                sku=plan_sku,
                reserved=False  # Not Linux
            )
            
            plan_poller = self.web_client.app_service_plans.begin_create_or_update(
                resource_group,
                plan_name,
                plan
            )
            await plan_poller.result()
            
            # Create web app
            site_config = SiteConfig(
                java_version=None,
                python_version=app_config.get("python_version"),
                node_version=app_config.get("node_version"),
                https_only=app_config.get("https_only", True)
            )
            
            site = Site(
                location=app_config["location"],
                site_config=site_config,
                server_farm_id=f"/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.Web/serverfarms/{plan_name}"
            )
            
            app_poller = self.web_client.web_apps.begin_create_or_update(
                resource_group,
                app_name,
                site
            )
            
            app_result = await app_poller.result()
            
            return {
                "success": True,
                "data": {
                    "id": str(app_result.id),
                    "name": app_result.name,
                    "default_hostname": app_result.default_host_name,
                    "app_service_plan": plan_name,
                    "status": "Creating"
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to deploy app service: {e}")
            return {
                "success": False,
                "error": str(e)
            }