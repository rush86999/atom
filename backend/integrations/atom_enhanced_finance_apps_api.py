"""
ATOM Enhanced Finance Apps API Integration
Comprehensive API integration for enhanced finance applications
"""

from fastapi import APIRouter, HTTPException, BackgroundTasks, Query, Body, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Dict, List, Any, Optional
from datetime import datetime, timedelta
import json
import logging
import asyncio
from dataclasses import asdict

from integrations.atom_communication_ingestion_pipeline import memory_manager
from integrations.atom_enhanced_finance_apps_enhancement import finance_apps_enhancement, FinanceAppType

logger = logging.getLogger(__name__)
security = HTTPBearer()

class AtomEnhancedFinanceAppsAPI:
    """Enhanced API integration for ATOM finance applications"""
    
    def __init__(self):
        self.router = APIRouter(
            prefix="/api/atom/finance",
            tags=["ATOM Enhanced Finance Apps"]
        )
        self.setup_routes()
        self.setup_webhook_handlers()
    
    def setup_webhook_handlers(self):
        """Setup webhook handlers for finance apps"""
        self.webhook_handlers = {
            'quickbooks': self._handle_quickbooks_webhook,
            'stripe': self._handle_stripe_webhook,
            'plaid': self._handle_plaid_webhook,
            'ramp': self._handle_ramp_webhook,
            'gusto': self._handle_gusto_webhook,
            'coupa': self._handle_coupa_webhook
        }
    
    def setup_routes(self):
        """Setup enhanced finance apps API routes"""
        
        @self.router.get("/apps")
        async def get_enhanced_finance_apps():
            """Get all enhanced finance apps with configurations"""
            try:
                apps = []
                for app_type in FinanceAppType:
                    config = finance_apps_enhancement.enhanced_configs.get(app_type.value)
                    
                    app_info = {
                        "id": app_type.value,
                        "name": config.get("name", app_type.value.replace("_", " ").title()),
                        "category": config.get("category", "general"),
                        "description": config.get("description", ""),
                        "features": config.get("features", []),
                        "supported_entities": config.get("supported_entities", []),
                        "real_time_sync": config.get("real_time_sync", False),
                        "webhooks_enabled": config.get("webhooks", False),
                        "api_version": config.get("api_version", "v1"),
                        "batch_size": config.get("batch_size", 100),
                        "data_retention_days": config.get("data_retention_days", 365)
                    }
                    apps.append(app_info)
                
                return {
                    "apps": apps,
                    "total": len(apps),
                    "categories": list(set(app["category"] for app in apps)),
                    "timestamp": datetime.now().isoformat(),
                    "version": "2.0.0"
                }
            except Exception as e:
                logger.error(f"Error getting finance apps: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/apps/{app_id}")
        async def get_finance_app_details(app_id: str):
            """Get detailed information for a specific finance app"""
            try:
                # Validate app_id
                FinanceAppType(app_id)
                
                # Get app configuration
                config = finance_apps_enhancement.enhanced_configs.get(app_id)
                if not config:
                    raise HTTPException(status_code=404, detail=f"Finance app {app_id} not found")
                
                # Get app statistics from memory
                app_stats = await self._get_app_statistics(app_id)
                
                return {
                    "app_id": app_id,
                    "name": config.get("name"),
                    "category": config.get("category"),
                    "description": config.get("description"),
                    "features": config.get("features", []),
                    "supported_entities": config.get("supported_entities", []),
                    "configuration": {
                        "api_version": config.get("api_version", "v1"),
                        "real_time_sync": config.get("real_time_sync", False),
                        "webhooks_enabled": config.get("webhooks", False),
                        "batch_size": config.get("batch_size", 100),
                        "data_retention_days": config.get("data_retention_days", 365)
                    },
                    "statistics": app_stats,
                    "endpoints": await self._get_app_endpoints(app_id),
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error getting finance app details: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/apps/{app_id}/sync")
        async def sync_finance_app_data(
            app_id: str,
            sync_config: Dict[str, Any] = Body(..., description="Sync configuration"),
            token: str = Depends(security.verify_token)
        ):
            """Sync data from a finance app"""
            try:
                # Validate app_id
                FinanceAppType(app_id)
                
                # Start sync process
                sync_result = await finance_apps_enhancement.sync_finance_app(
                    app_id, sync_config
                )
                
                return {
                    "success": True,
                    "app_id": app_id,
                    "sync_id": sync_result.get("sync_id"),
                    "status": sync_result.get("status"),
                    "records_processed": sync_result.get("records_processed", 0),
                    "started_at": sync_result.get("started_at"),
                    "estimated_completion": sync_result.get("estimated_completion"),
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error syncing finance app data: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/apps/{app_id}/ingest")
        async def ingest_finance_data(
            app_id: str,
            data_type: str = Query(..., description="Type of financial data"),
            finance_data: List[Dict[str, Any]] = Body(..., description="Financial data to ingest"),
            token: str = Depends(security.verify_token)
        ):
            """Ingest financial data from an app"""
            try:
                # Validate app_id
                FinanceAppType(app_id)
                
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Ingest finance data
                success_count = 0
                for data in finance_data:
                    enhanced_data = await finance_apps_enhancement.enhance_finance_data(
                        app_id, data_type, data
                    )
                    
                    success = await finance_apps_enhancement.ingest_finance_data(
                        app_id, enhanced_data
                    )
                    if success:
                        success_count += 1
                
                return {
                    "success": True,
                    "app_id": app_id,
                    "data_type": data_type,
                    "total_records": len(finance_data),
                    "successful_ingestion": success_count,
                    "failed_ingestion": len(finance_data) - success_count,
                    "success_rate": f"{(success_count / len(finance_data)) * 100:.1f}%",
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error ingesting finance data: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/analytics")
        async def get_finance_analytics(
            app_id: Optional[str] = Query(None, description="Filter by app ID"),
            data_type: Optional[str] = Query(None, description="Filter by data type"),
            time_start: Optional[str] = Query(None, description="Start date (ISO format)"),
            time_end: Optional[str] = Query(None, description="End date (ISO format)"),
            token: str = Depends(security.verify_token)
        ):
            """Get comprehensive finance analytics"""
            try:
                # Initialize memory manager if needed
                if not memory_manager.db:
                    memory_manager.initialize()
                
                # Build analytics query
                analytics_data = await finance_apps_enhancement.get_finance_analytics(
                    app_id=app_id,
                    data_type=data_type,
                    time_start=time_start,
                    time_end=time_end
                )
                
                return {
                    "success": True,
                    "analytics": analytics_data,
                    "filters": {
                        "app_id": app_id,
                        "data_type": data_type,
                        "time_range": {"start": time_start, "end": time_end}
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting finance analytics: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/financial-health")
        async def get_financial_health(
            company_id: Optional[str] = Query(None, description="Company ID"),
            time_period: str = Query("30d", description="Time period"),
            token: str = Depends(security.verify_token)
        ):
            """Get comprehensive financial health metrics"""
            try:
                # Get financial health metrics
                health_data = await finance_apps_enhancement.get_financial_health(
                    company_id=company_id,
                    time_period=time_period
                )
                
                return {
                    "success": True,
                    "financial_health": health_data,
                    "company_id": company_id,
                    "time_period": time_period,
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error getting financial health: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.post("/webhooks/{app_id}")
        async def handle_finance_webhook(
            app_id: str,
            request: Request,
            background_tasks: BackgroundTasks,
            token: str = Depends(security.verify_token)
        ):
            """Handle webhook from finance app"""
            try:
                # Validate app_id
                FinanceAppType(app_id)
                
                # Get webhook data
                webhook_data = await request.json()
                
                # Add to background processing
                background_tasks.add_task(
                    self._process_finance_webhook,
                    app_id, webhook_data
                )
                
                return {
                    "success": True,
                    "message": f"Webhook from {app_id} received for processing",
                    "app_id": app_id,
                    "timestamp": datetime.now().isoformat()
                }
                
            except ValueError:
                raise HTTPException(status_code=404, detail=f"Invalid app_id: {app_id}")
            except Exception as e:
                logger.error(f"Error handling finance webhook: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
        
        @self.router.get("/reports")
        async def get_finance_reports(
            report_type: str = Query(..., description="Type of report"),
            app_id: Optional[str] = Query(None, description="Filter by app ID"),
            time_start: Optional[str] = Query(None, description="Start date (ISO format)"),
            time_end: Optional[str] = Query(None, description="End date (ISO format)"),
            token: str = Depends(security.verify_token)
        ):
            """Generate financial reports"""
            try:
                # Generate report
                report_data = await finance_apps_enhancement.generate_finance_report(
                    report_type=report_type,
                    app_id=app_id,
                    time_start=time_start,
                    time_end=time_end
                )
                
                return {
                    "success": True,
                    "report": report_data,
                    "report_type": report_type,
                    "filters": {
                        "app_id": app_id,
                        "time_range": {"start": time_start, "end": time_end}
                    },
                    "timestamp": datetime.now().isoformat()
                }
                
            except Exception as e:
                logger.error(f"Error generating finance report: {str(e)}")
                raise HTTPException(status_code=500, detail=str(e))
    
    async def _get_app_statistics(self, app_id: str) -> Dict[str, Any]:
        """Get statistics for a finance app"""
        try:
            if memory_manager.finance_table:
                # Get app statistics from database
                df = memory_manager.finance_table.to_pandas()
                app_df = df[df["app_type"] == app_id]
                
                if not app_df.empty:
                    return {
                        "total_records": len(app_df),
                        "data_types": app_df["data_type"].value_counts().to_dict(),
                        "date_range": {
                            "earliest": app_df["timestamp"].min(),
                            "latest": app_df["timestamp"].max()
                        },
                        "last_sync": app_df["timestamp"].max()
                    }
            
            return {
                "total_records": 0,
                "data_types": {},
                "date_range": {"earliest": None, "latest": None},
                "last_sync": None
            }
            
        except Exception as e:
            logger.error(f"Error getting app statistics: {str(e)}")
            return {"error": str(e)}
    
    async def _get_app_endpoints(self, app_id: str) -> List[str]:
        """Get available endpoints for a finance app"""
        try:
            config = finance_apps_enhancement.enhanced_configs.get(app_id, {})
            
            endpoints = [
                f"/api/atom/finance/apps/{app_id}",
                f"/api/atom/finance/apps/{app_id}/sync",
                f"/api/atom/finance/apps/{app_id}/ingest",
                f"/api/atom/finance/apps/{app_id}/analytics"
            ]
            
            if config.get("webhooks", False):
                endpoints.append(f"/api/atom/finance/webhooks/{app_id}")
            
            return endpoints
            
        except Exception as e:
            logger.error(f"Error getting app endpoints: {str(e)}")
            return []
    
    async def _process_finance_webhook(self, app_id: str, webhook_data: Dict[str, Any]):
        """Process webhook from finance app in background"""
        try:
            # Get webhook handler for app
            handler = self.webhook_handlers.get(app_id)
            if handler:
                await handler(webhook_data)
            else:
                logger.warning(f"No webhook handler found for app: {app_id}")
                
        except Exception as e:
            logger.error(f"Error processing finance webhook: {str(e)}")
    
    async def _handle_quickbooks_webhook(self, webhook_data: Dict[str, Any]):
        """Handle QuickBooks webhook"""
        try:
            # Process QuickBooks webhook data
            enhanced_data = await finance_apps_enhancement.enhance_quickbooks_data(webhook_data)
            await finance_apps_enhancement.ingest_finance_data("quickbooks", enhanced_data)
            
        except Exception as e:
            logger.error(f"Error handling QuickBooks webhook: {str(e)}")
    
    async def _handle_stripe_webhook(self, webhook_data: Dict[str, Any]):
        """Handle Stripe webhook"""
        try:
            # Process Stripe webhook data
            enhanced_data = await finance_apps_enhancement.enhance_stripe_data(webhook_data)
            await finance_apps_enhancement.ingest_finance_data("stripe", enhanced_data)
            
        except Exception as e:
            logger.error(f"Error handling Stripe webhook: {str(e)}")
    
    async def _handle_plaid_webhook(self, webhook_data: Dict[str, Any]):
        """Handle Plaid webhook"""
        try:
            # Process Plaid webhook data
            enhanced_data = await finance_apps_enhancement.enhance_plaid_data(webhook_data)
            await finance_apps_enhancement.ingest_finance_data("plaid", enhanced_data)
            
        except Exception as e:
            logger.error(f"Error handling Plaid webhook: {str(e)}")
    
    async def _handle_ramp_webhook(self, webhook_data: Dict[str, Any]):
        """Handle Ramp webhook"""
        try:
            # Process Ramp webhook data
            enhanced_data = await finance_apps_enhancement.enhance_ramp_data(webhook_data)
            await finance_apps_enhancement.ingest_finance_data("ramp", enhanced_data)
            
        except Exception as e:
            logger.error(f"Error handling Ramp webhook: {str(e)}")
    
    async def _handle_gusto_webhook(self, webhook_data: Dict[str, Any]):
        """Handle Gusto webhook"""
        try:
            # Process Gusto webhook data
            enhanced_data = await finance_apps_enhancement.enhance_gusto_data(webhook_data)
            await finance_apps_enhancement.ingest_finance_data("gusto", enhanced_data)
            
        except Exception as e:
            logger.error(f"Error handling Gusto webhook: {str(e)}")
    
    async def _handle_coupa_webhook(self, webhook_data: Dict[str, Any]):
        """Handle Coupa webhook"""
        try:
            # Process Coupa webhook data
            enhanced_data = await finance_apps_enhancement.enhance_coupa_data(webhook_data)
            await finance_apps_enhancement.ingest_finance_data("coupa", enhanced_data)
            
        except Exception as e:
            logger.error(f"Error handling Coupa webhook: {str(e)}")
    
    def get_router(self):
        """Get the configured router"""
        return self.router

# Create global instance
atom_enhanced_finance_apps_api = AtomEnhancedFinanceAppsAPI()
atom_enhanced_finance_apps_router = atom_enhanced_finance_apps_api.get_router()

# Export for main app
__all__ = [
    'AtomEnhancedFinanceAppsAPI',
    'atom_enhanced_finance_apps_api',
    'atom_enhanced_finance_apps_router'
]
