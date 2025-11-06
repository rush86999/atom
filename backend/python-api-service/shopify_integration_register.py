"""
Shopify Integration Registration
Registration utilities for Shopify integration with ATOM backend
"""

import logging
from flask import Flask, Blueprint
from typing import Optional, Dict, Any

from shopify_routes import register_shopify_blueprints, set_database_pool
from shopify_service import ShopifyService
from shopify_webhooks import get_webhook_processor, setup_default_handlers
from shopify_bulk_api import ShopifyBulkAPI
from shopify_custom_apps import ShopifyCustomApps
from shopify_analytics import ShopifyAnalytics

logger = logging.getLogger(__name__)

def register_shopify_integration(app: Flask, db_pool=None) -> bool:
    """Register Shopify integration with Flask app"""
    try:
        # Set database pool for Shopify services
        if db_pool:
            set_database_pool(db_pool)
            logger.info("Database pool set for Shopify integration")
        
        # Register Shopify blueprints
        success = register_shopify_blueprints(app)
        if not success:
            logger.error("Failed to register Shopify blueprints")
            return False
        
        # Initialize Shopify services
        _init_shopify_services()
        
        logger.info("✅ Shopify integration registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"❌ Error registering Shopify integration: {e}")
        return False

def _init_shopify_services():
    """Initialize Shopify services"""
    try:
        # Initialize global Shopify service
        global_shopify_service = ShopifyService()
        
        # Setup webhook processor (will be configured when needed)
        webhook_processor = get_webhook_processor()
        if webhook_processor:
            setup_default_handlers(webhook_processor)
            logger.info("Default Shopify webhook handlers configured")
        
        logger.info("Shopify services initialized")
        
    except Exception as e:
        logger.error(f"Error initializing Shopify services: {e}")

def get_shopify_endpoints() -> Dict[str, Any]:
    """Get Shopify integration endpoints"""
    return {
        "core": {
            "health": "/api/shopify/health",
            "connect": "/api/shopify/connect",
            "products": "/api/shopify/products",
            "orders": "/api/shopify/orders",
            "customers": "/api/shopify/customers",
            "search": "/api/shopify/search",
            "shop": "/api/shopify/shop"
        },
        "webhooks": {
            "setup": "/api/shopify/webhooks/setup",
            "handle": "/api/shopify/webhooks/<topic>",
            "events": "/api/shopify/webhooks/events",
            "topics": "/api/shopify/webhooks/topics"
        },
        "bulk": {
            "query": "/api/shopify/bulk/query",
            "operations": "/api/shopify/bulk/operations/<operation_id>",
            "wait": "/api/shopify/bulk/operations/<operation_id>/wait",
            "products": "/api/shopify/bulk/products",
            "orders": "/api/shopify/bulk/orders",
            "create_products": "/api/shopify/bulk/products/create"
        },
        "custom_apps": {
            "apps": "/api/shopify/apps",
            "extensions": "/api/shopify/apps/<app_id>/extensions",
            "install": "/api/shopify/apps/<app_id>/install",
            "permissions": "/api/shopify/apps/<app_id>/permissions",
            "installations": "/api/shopify/installations"
        },
        "analytics": {
            "sales": "/api/shopify/analytics/sales",
            "customers": "/api/shopify/analytics/customers",
            "products": "/api/shopify/analytics/products",
            "inventory": "/api/shopify/analytics/inventory",
            "report": "/api/shopify/analytics/report",
            "forecast": "/api/shopify/analytics/forecast"
        }
    }

def get_shopify_service_info() -> Dict[str, Any]:
    """Get Shopify service information"""
    return {
        "name": "Shopify Integration",
        "version": "1.0.0",
        "description": "Complete Shopify e-commerce and store management service",
        "features": {
            "core": {
                "products": "Product management (CRUD, search, filtering)",
                "orders": "Order management (creation, tracking, fulfillment)",
                "customers": "Customer management (profiles, segmentation)",
                "inventory": "Inventory tracking and management",
                "search": "Cross-entity search functionality"
            },
            "webhooks": {
                "real_time": "Real-time event notifications",
                "topics": "Support for all Shopify webhook topics",
                "signature": "Webhook signature verification",
                "processing": "Asynchronous event processing",
                "history": "Event history and statistics"
            },
            "bulk_operations": {
                "graphql": "Bulk GraphQL operations",
                "products": "Bulk product operations",
                "orders": "Bulk order operations",
                "customers": "Bulk customer operations",
                "inventory": "Bulk inventory operations",
                "status": "Operation status tracking"
            },
            "custom_apps": {
                "creation": "Custom app development",
                "extensions": "App extensions support",
                "installation": "App installation management",
                "permissions": "Granular permission control",
                "oauth": "OAuth flow management"
            },
            "analytics": {
                "sales": "Sales analytics and reporting",
                "customers": "Customer analytics and segmentation",
                "products": "Product performance analytics",
                "inventory": "Inventory analytics and optimization",
                "forecasting": "Sales forecasting and predictions",
                "reports": "Comprehensive reporting dashboard"
            }
        },
        "api_version": "2024-01",
        "endpoints": get_shopify_endpoints(),
        "phase": "Phase 1 - Complete",
        "roadmap": {
            "phase_1": {
                "status": "✅ Complete",
                "features": [
                    "Real-time Webhooks",
                    "Bulk API Integration", 
                    "Custom App Extension",
                    "Advanced Analytics"
                ]
            },
            "phase_2": {
                "status": "🔄 Planned Q2 2025",
                "features": [
                    "AI-Powered Insights",
                    "Automated Inventory",
                    "Multi-channel Sales",
                    "Advanced Customer Segmentation"
                ]
            },
            "phase_3": {
                "status": "📋 Planned H2 2025", 
                "features": [
                    "Predictive Analytics",
                    "Automated Marketing",
                    "Supply Chain Optimization",
                    "International Expansion"
                ]
            }
        }
    }

# Export registration functions
__all__ = [
    "register_shopify_integration",
    "get_shopify_endpoints",
    "get_shopify_service_info"
]