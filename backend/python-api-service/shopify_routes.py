"""
Shopify API Routes
Flask routes for Shopify integration including webhooks, bulk operations, custom apps, and analytics
"""

from flask import Blueprint, request, jsonify, current_app
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger
import asyncio
import json

# Import Shopify services
from shopify_service import ShopifyService, ShopifyServiceConfig, get_shopify_client
from shopify_webhooks import ShopifyWebhookProcessor, get_webhook_processor, setup_default_handlers
from shopify_bulk_api import ShopifyBulkAPI, BulkOperationStatus
from shopify_custom_apps import ShopifyCustomApps, ShopifyCustomApp, AppExtension, AppPermission
from shopify_analytics import (
    ShopifyAnalytics, 
    SalesAnalytics, 
    CustomerAnalytics, 
    ProductAnalytics, 
    InventoryAnalytics,
    TimeGranularity
)

# Initialize Shopify service
shopify_service = ShopifyService()

# Create Flask blueprints
shopify_bp = Blueprint("shopify_bp", __name__)
shopify_webhooks_bp = Blueprint("shopify_webhooks_bp", __name__)
shopify_bulk_bp = Blueprint("shopify_bulk_bp", __name__)
shopify_apps_bp = Blueprint("shopify_apps_bp", __name__)
shopify_analytics_bp = Blueprint("shopify_analytics_bp", __name__)

# Database pool (will be set from main app)
db_pool = None

def set_database_pool(pool):
    """Set database connection pool"""
    global db_pool
    db_pool = pool

# =============================================================================
# Core Shopify API Routes
# =============================================================================

@shopify_bp.route('/api/shopify/health', methods=['GET'])
async def shopify_health():
    """Check Shopify integration health"""
    try:
        health_status = {
            "status": "healthy",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "services": {
                "shopify_service": True,
                "database": db_pool is not None,
                "webhook_processor": get_webhook_processor() is not None
            },
            "api_version": "2024-01",
            "features": {
                "webhooks": True,
                "bulk_operations": True,
                "custom_apps": True,
                "analytics": True
            }
        }
        
        return jsonify({"ok": True, "health": health_status})
        
    except Exception as e:
        logger.error(f"Shopify health check error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/connect', methods=['POST'])
async def shopify_connect():
    """Connect to Shopify store"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        shop_domain = data.get('shop_domain')
        access_token = data.get('access_token')
        
        if not all([user_id, shop_domain, access_token]):
            return jsonify({
                "ok": False,
                "error": "user_id, shop_domain, and access_token are required"
            }), 400
        
        # Test connection by getting shop info
        test_shop_service = ShopifyService(ShopifyServiceConfig())
        
        # Override domain for this request
        response = await test_shop_service._make_request(
            user_id=user_id,
            method="GET",
            endpoint="shop",
            shop_domain=shop_domain,
            db_conn_pool=db_pool
        )
        
        if response and "shop" in response:
            shop_info = response["shop"]
            
            return jsonify({
                "ok": True,
                "connected": True,
                "shop": {
                    "id": shop_info.get("id"),
                    "name": shop_info.get("name"),
                    "domain": shop_info.get("domain"),
                    "email": shop_info.get("email"),
                    "currency": shop_info.get("currency"),
                    "timezone": shop_info.get("timezone")
                },
                "message": "Successfully connected to Shopify store"
            })
        else:
            return jsonify({
                "ok": False,
                "connected": False,
                "error": "Failed to connect to Shopify store"
            }), 400
            
    except Exception as e:
        logger.error(f"Shopify connection error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/products', methods=['GET'])
async def get_products():
    """Get Shopify products"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get filters
        status = request.args.get('status')
        product_type = request.args.get('product_type')
        vendor = request.args.get('vendor')
        created_at_min = request.args.get('created_at_min')
        created_at_max = request.args.get('created_at_max')
        limit = int(request.args.get('limit', 50))
        
        # Get products
        products = await shopify_service.get_products(
            user_id=user_id,
            status=status,
            product_type=product_type,
            vendor=vendor,
            created_at_min=created_at_min,
            created_at_max=created_at_max,
            limit=limit,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": True,
            "products": products,
            "total": len(products),
            "filters": {
                "status": status,
                "product_type": product_type,
                "vendor": vendor,
                "created_at_min": created_at_min,
                "created_at_max": created_at_max,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting products: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/products', methods=['POST'])
async def create_product():
    """Create new Shopify product"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        product_data = data.get('product', {})
        
        if not user_id or not product_data:
            return jsonify({
                "ok": False,
                "error": "user_id and product data are required"
            }), 400
        
        # Create product
        result = await shopify_service.create_product(
            user_id=user_id,
            product_data=product_data,
            db_conn_pool=db_pool
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating product: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/orders', methods=['GET'])
async def get_orders():
    """Get Shopify orders"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get filters
        status = request.args.get('status')
        fulfillment_status = request.args.get('fulfillment_status')
        created_at_min = request.args.get('created_at_min')
        created_at_max = request.args.get('created_at_max')
        limit = int(request.args.get('limit', 50))
        
        # Get orders
        orders = await shopify_service.get_orders(
            user_id=user_id,
            status=status,
            fulfillment_status=fulfillment_status,
            created_at_min=created_at_min,
            created_at_max=created_at_max,
            limit=limit,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": True,
            "orders": orders,
            "total": len(orders),
            "filters": {
                "status": status,
                "fulfillment_status": fulfillment_status,
                "created_at_min": created_at_min,
                "created_at_max": created_at_max,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting orders: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/orders', methods=['POST'])
async def create_order():
    """Create new Shopify order"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        order_data = data.get('order', {})
        
        if not user_id or not order_data:
            return jsonify({
                "ok": False,
                "error": "user_id and order data are required"
            }), 400
        
        # Create order
        result = await shopify_service.create_order(
            user_id=user_id,
            order_data=order_data,
            db_conn_pool=db_pool
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating order: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/customers', methods=['GET'])
async def get_customers():
    """Get Shopify customers"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get filters
        email = request.args.get('email')
        limit = int(request.args.get('limit', 50))
        
        # Get customers
        customers = await shopify_service.get_customers(
            user_id=user_id,
            email=email,
            limit=limit,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": True,
            "customers": customers,
            "total": len(customers),
            "filters": {
                "email": email,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting customers: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/customers', methods=['POST'])
async def create_customer():
    """Create new Shopify customer"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        customer_data = data.get('customer', {})
        
        if not user_id or not customer_data:
            return jsonify({
                "ok": False,
                "error": "user_id and customer data are required"
            }), 400
        
        # Create customer
        result = await shopify_service.create_customer(
            user_id=user_id,
            customer_data=customer_data,
            db_conn_pool=db_pool
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating customer: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/search', methods=['POST'])
async def search_shopify():
    """Search across Shopify data"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        search_type = data.get('type', 'all')
        limit = int(data.get('limit', 20))
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        if not query:
            return jsonify({"ok": False, "error": "query is required"}), 400
        
        # Search
        results = await shopify_service.search_shopify(
            user_id=user_id,
            query=query,
            search_type=search_type,
            limit=limit,
            db_conn_pool=db_pool
        )
        
        return jsonify({
            "ok": True,
            "query": query,
            "search_type": search_type,
            "results": results,
            "total": sum(len(v) for v in results.values())
        })
        
    except Exception as e:
        logger.error(f"Error searching Shopify: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bp.route('/api/shopify/shop', methods=['GET'])
async def get_shop_info():
    """Get shop information"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get shop info
        result = await shopify_service.get_shop_info(
            user_id=user_id,
            db_conn_pool=db_pool
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error getting shop info: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Shopify Webhooks Routes
# =============================================================================

@shopify_webhooks_bp.route('/api/shopify/webhooks/setup', methods=['POST'])
async def setup_webhooks():
    """Setup Shopify webhooks"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        webhook_secret = data.get('webhook_secret')
        webhook_url = data.get('webhook_url')
        
        if not all([user_id, webhook_secret, webhook_url]):
            return jsonify({
                "ok": False,
                "error": "user_id, webhook_secret, and webhook_url are required"
            }), 400
        
        # Get webhook processor
        processor = get_webhook_processor(webhook_secret)
        
        # Setup default handlers
        setup_default_handlers(processor)
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Register webhooks
        webhook_topics = [
            "orders/create",
            "orders/paid",
            "orders/cancelled",
            "products/create",
            "products/update",
            "customers/create",
            "customers/update",
            "inventory_levels/update"
        ]
        
        registered_webhooks = []
        for topic in webhook_topics:
            result = await shopify_client.register_webhook(
                topic=topic,
                address=webhook_url,
                format="json"
            )
            
            if result.get('success'):
                registered_webhooks.append({
                    "topic": topic,
                    "webhook_id": result.get('webhook').id,
                    "address": webhook_url
                })
        
        return jsonify({
            "ok": True,
            "webhooks_registered": len(registered_webhooks),
            "webhooks": registered_webhooks,
            "message": f"Successfully setup {len(registered_webhooks)} webhooks"
        })
        
    except Exception as e:
        logger.error(f"Error setting up webhooks: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks/<topic>', methods=['POST'])
async def handle_webhook(topic: str):
    """Handle incoming Shopify webhook"""
    try:
        # Get webhook processor
        processor = get_webhook_processor()
        if not processor:
            logger.error("Webhook processor not initialized")
            return jsonify({"error": "Webhook processor not initialized"}), 500
        
        # Parse webhook event
        event = processor.parse_webhook_event(request)
        if not event:
            return jsonify({"error": "Invalid webhook event"}), 400
        
        # Verify topic matches
        if event.topic.replace("/", "_") != topic.replace("/", "_"):
            logger.error(f"Topic mismatch: expected {topic}, got {event.topic}")
            return jsonify({"error": "Topic mismatch"}), 400
        
        # Process event
        success = await processor.process_event(event)
        
        if success:
            return jsonify({"status": "success", "event_id": event.id}), 200
        else:
            return jsonify({"error": "Event processing failed"}), 500
            
    except Exception as e:
        logger.error(f"Error handling webhook: {e}")
        return jsonify({"error": str(e)}), 500

@shopify_webhooks_bp.route('/api/shopify/webhooks/events', methods=['GET'])
async def get_webhook_events():
    """Get webhook event history"""
    try:
        topic = request.args.get('topic')
        shop_domain = request.args.get('shop_domain')
        limit = int(request.args.get('limit', 100))
        include_stats = request.args.get('include_stats', 'true').lower() == 'true'
        
        # Get webhook processor
        processor = get_webhook_processor()
        if not processor:
            return jsonify({"ok": False, "error": "Webhook processor not initialized"}), 500
        
        # Get event history
        events = processor.get_event_history(topic, shop_domain, limit)
        
        response = {
            "ok": True,
            "events": [
                {
                    "id": event.id,
                    "topic": event.topic,
                    "shop_domain": event.shop_domain,
                    "timestamp": event.timestamp.isoformat(),
                    "processed": event.processed,
                    "processing_error": event.processing_error
                }
                for event in events
            ],
            "total": len(events)
        }
        
        # Include statistics if requested
        if include_stats:
            response["statistics"] = processor.get_event_statistics()
        
        return jsonify(response)
        
    except Exception as e:
        logger.error(f"Error getting webhook events: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Shopify Bulk Operations Routes
# =============================================================================

@shopify_bulk_bp.route('/api/shopify/bulk/query', methods=['POST'])
async def execute_bulk_query():
    """Execute bulk GraphQL query"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        variables = data.get('variables', {})
        
        if not user_id or not query:
            return jsonify({
                "ok": False,
                "error": "user_id and query are required"
            }), 400
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Initialize bulk API
        bulk_api = ShopifyBulkAPI(shopify_client)
        
        # Execute bulk query
        result = await bulk_api.create_bulk_query(query, variables)
        
        if result.success:
            # Wait for completion if requested
            wait_for_completion = data.get('wait_for_completion', False)
            if wait_for_completion:
                completion_result = await bulk_api.wait_for_operation_completion(result.operation_id)
                return jsonify({
                    "ok": True,
                    "operation_id": result.operation_id,
                    "completed": True,
                    "data": completion_result.data,
                    "total_count": completion_result.total_count,
                    "errors": completion_result.errors
                })
            else:
                return jsonify({
                    "ok": True,
                    "operation_id": result.operation_id,
                    "file_url": result.file_url,
                    "status": "running"
                })
        else:
            return jsonify({
                "ok": False,
                "error": result.errors
            }), 400
        
    except Exception as e:
        logger.error(f"Error executing bulk query: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bulk_bp.route('/api/shopify/bulk/operations/<operation_id>/status', methods=['GET'])
async def get_bulk_operation_status(operation_id: str):
    """Get bulk operation status"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Initialize bulk API
        bulk_api = ShopifyBulkAPI(shopify_client)
        
        # Check operation status
        operation = await bulk_api.check_operation_status(operation_id)
        
        if operation:
            return jsonify({
                "ok": True,
                "operation": {
                    "id": operation.id,
                    "status": operation.status.value,
                    "created_at": operation.created_at.isoformat(),
                    "completed_at": operation.completed_at.isoformat() if operation.completed_at else None,
                    "object_count": operation.object_count,
                    "file_size": operation.file_size,
                    "url": operation.url,
                    "error_code": operation.error_code,
                    "error_message": operation.error_message
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Operation not found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting bulk operation status: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bulk_bp.route('/api/shopify/bulk/operations/<operation_id>/wait', methods=['GET'])
async def wait_for_bulk_operation(operation_id: str):
    """Wait for bulk operation completion"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Initialize bulk API
        bulk_api = ShopifyBulkAPI(shopify_client)
        
        # Wait for completion
        result = await bulk_api.wait_for_operation_completion(operation_id)
        
        return jsonify({
            "ok": result.success,
            "operation_id": result.operation_id,
            "data": result.data,
            "total_count": result.total_count,
            "errors": result.errors,
            "processing_time": result.processing_time
        })
        
    except Exception as e:
        logger.error(f"Error waiting for bulk operation: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# Predefined bulk operations
@shopify_bulk_bp.route('/api/shopify/bulk/products', methods=['GET'])
async def bulk_get_products():
    """Bulk get products"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get filters
        product_ids = request.args.getlist('product_ids')
        collection_id = request.args.get('collection_id')
        status = request.args.get('status')
        limit = int(request.args.get('limit', 250))
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Initialize bulk API
        bulk_api = ShopifyBulkAPI(shopify_client)
        
        # Execute bulk products query
        result = await bulk_api.bulk_get_products(
            product_ids=product_ids if product_ids else None,
            collection_id=collection_id,
            status=status,
            limit=limit
        )
        
        if result.success:
            # Wait for completion
            completion_result = await bulk_api.wait_for_operation_completion(result.operation_id)
            
            return jsonify({
                "ok": True,
                "operation_id": result.operation_id,
                "products": completion_result.data,
                "total_count": completion_result.total_count,
                "errors": completion_result.errors
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.errors
            }), 400
        
    except Exception as e:
        logger.error(f"Error in bulk get products: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bulk_bp.route('/api/shopify/bulk/orders', methods=['GET'])
async def bulk_get_orders():
    """Bulk get orders"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Get filters
        order_ids = request.args.getlist('order_ids')
        created_at_min = request.args.get('created_at_min')
        created_at_max = request.args.get('created_at_max')
        financial_status = request.args.get('financial_status')
        limit = int(request.args.get('limit', 250))
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Initialize bulk API
        bulk_api = ShopifyBulkAPI(shopify_client)
        
        # Execute bulk orders query
        result = await bulk_api.bulk_get_orders(
            order_ids=order_ids if order_ids else None,
            created_at_min=created_at_min,
            created_at_max=created_at_max,
            financial_status=financial_status,
            limit=limit
        )
        
        if result.success:
            # Wait for completion
            completion_result = await bulk_api.wait_for_operation_completion(result.operation_id)
            
            return jsonify({
                "ok": True,
                "operation_id": result.operation_id,
                "orders": completion_result.data,
                "total_count": completion_result.total_count,
                "errors": completion_result.errors
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.errors
            }), 400
        
    except Exception as e:
        logger.error(f"Error in bulk get orders: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_bulk_bp.route('/api/shopify/bulk/products/create', methods=['POST'])
async def bulk_create_products():
    """Bulk create products"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        products = data.get('products', [])
        
        if not user_id or not products:
            return jsonify({
                "ok": False,
                "error": "user_id and products are required"
            }), 400
        
        if len(products) > 100:
            return jsonify({
                "ok": False,
                "error": "Maximum 100 products per bulk operation"
            }), 400
        
        # Get Shopify client
        shopify_client = await get_shopify_client(user_id, db_pool)
        if not shopify_client:
            return jsonify({
                "ok": False,
                "error": "Failed to get Shopify client"
            }), 500
        
        # Initialize bulk API
        bulk_api = ShopifyBulkAPI(shopify_client)
        
        # Execute bulk create products
        result = await bulk_api.bulk_create_products(products)
        
        if result.success:
            # Wait for completion
            completion_result = await bulk_api.wait_for_operation_completion(result.operation_id)
            
            return jsonify({
                "ok": True,
                "operation_id": result.operation_id,
                "results": completion_result.data,
                "total_count": completion_result.total_count,
                "errors": completion_result.errors
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.errors
            }), 400
        
    except Exception as e:
        logger.error(f"Error in bulk create products: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Shopify Custom Apps Routes
# =============================================================================

@shopify_apps_bp.route('/api/shopify/apps', methods=['POST'])
async def create_custom_app():
    """Create custom Shopify app"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        app_data = data.get('app', {})
        
        if not user_id or not app_data:
            return jsonify({
                "ok": False,
                "error": "user_id and app data are required"
            }), 400
        
        # Initialize custom apps manager
        custom_apps = ShopifyCustomApps(shopify_service, db_pool)
        
        # Create app
        result = await custom_apps.create_custom_app(user_id, app_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating custom app: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_apps_bp.route('/api/shopify/apps', methods=['GET'])
async def get_custom_apps():
    """Get custom Shopify apps"""
    try:
        user_id = request.args.get('user_id')
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Initialize custom apps manager
        custom_apps = ShopifyCustomApps(shopify_service, db_pool)
        
        # Get apps
        apps = await custom_apps.get_custom_apps(user_id)
        
        return jsonify({
            "ok": True,
            "apps": apps,
            "total": len(apps)
        })
        
    except Exception as e:
        logger.error(f"Error getting custom apps: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_apps_bp.route('/api/shopify/apps/<app_id>/extensions', methods=['POST'])
async def create_app_extension():
    """Create app extension"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        app_id = data.get('app_id')
        extension_data = data.get('extension', {})
        
        if not user_id or not app_id or not extension_data:
            return jsonify({
                "ok": False,
                "error": "user_id, app_id, and extension data are required"
            }), 400
        
        # Initialize custom apps manager
        custom_apps = ShopifyCustomApps(shopify_service, db_pool)
        
        # Create extension
        result = await custom_apps.create_app_extension(user_id, app_id, extension_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error creating app extension: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_apps_bp.route('/api/shopify/apps/<app_id>/install', methods=['POST'])
async def install_app():
    """Install app on shop"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        app_id = data.get('app_id')
        shop_domain = data.get('shop_domain')
        granted_scopes = data.get('granted_scopes', [])
        
        if not user_id or not app_id or not shop_domain:
            return jsonify({
                "ok": False,
                "error": "user_id, app_id, and shop_domain are required"
            }), 400
        
        # Initialize custom apps manager
        custom_apps = ShopifyCustomApps(shopify_service, db_pool)
        
        # Install app
        result = await custom_apps.install_app(user_id, app_id, shop_domain, granted_scopes)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error installing app: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_apps_bp.route('/api/shopify/apps/<app_id>/permissions', methods=['PUT'])
async def update_app_permissions():
    """Update app permissions"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        app_id = data.get('app_id')
        permissions = data.get('permissions', [])
        
        if not user_id or not app_id or not permissions:
            return jsonify({
                "ok": False,
                "error": "user_id, app_id, and permissions are required"
            }), 400
        
        # Convert string permissions to enum
        permission_enums = [AppPermission(perm) for perm in permissions]
        
        # Initialize custom apps manager
        custom_apps = ShopifyCustomApps(shopify_service, db_pool)
        
        # Update permissions
        result = await custom_apps.update_app_permissions(user_id, app_id, permission_enums)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error updating app permissions: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_apps_bp.route('/api/shopify/installations', methods=['GET'])
async def get_app_installations():
    """Get app installations"""
    try:
        user_id = request.args.get('user_id')
        app_id = request.args.get('app_id')
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        # Initialize custom apps manager
        custom_apps = ShopifyCustomApps(shopify_service, db_pool)
        
        # Get installations
        installations = await custom_apps.get_app_installations(user_id, app_id)
        
        return jsonify({
            "ok": True,
            "installations": installations,
            "total": len(installations)
        })
        
    except Exception as e:
        logger.error(f"Error getting app installations: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Shopify Analytics Routes
# =============================================================================

@shopify_analytics_bp.route('/api/shopify/analytics/sales', methods=['POST'])
async def get_sales_analytics():
    """Get sales analytics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        granularity_str = data.get('granularity', 'daily')
        include_forecast = data.get('include_forecast', False)
        
        if not all([user_id, start_date_str, end_date_str]):
            return jsonify({
                "ok": False,
                "error": "user_id, start_date, and end_date are required"
            }), 400
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        granularity = TimeGranularity(granularity_str)
        
        # Initialize analytics engine
        analytics = ShopifyAnalytics(shopify_service, db_pool)
        
        # Get sales analytics
        sales_analytics = await analytics.get_sales_analytics(
            user_id, start_date, end_date, granularity, include_forecast
        )
        
        return jsonify({
            "ok": True,
            "analytics": sales_analytics.__dict__
        })
        
    except Exception as e:
        logger.error(f"Error getting sales analytics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_analytics_bp.route('/api/shopify/analytics/customers', methods=['POST'])
async def get_customer_analytics():
    """Get customer analytics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        include_cohort = data.get('include_cohort', True)
        
        if not all([user_id, start_date_str, end_date_str]):
            return jsonify({
                "ok": False,
                "error": "user_id, start_date, and end_date are required"
            }), 400
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Initialize analytics engine
        analytics = ShopifyAnalytics(shopify_service, db_pool)
        
        # Get customer analytics
        customer_analytics = await analytics.get_customer_analytics(
            user_id, start_date, end_date, include_cohort
        )
        
        return jsonify({
            "ok": True,
            "analytics": customer_analytics.__dict__
        })
        
    except Exception as e:
        logger.error(f"Error getting customer analytics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_analytics_bp.route('/api/shopify/analytics/products', methods=['POST'])
async def get_product_analytics():
    """Get product analytics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        
        if not all([user_id, start_date_str, end_date_str]):
            return jsonify({
                "ok": False,
                "error": "user_id, start_date, and end_date are required"
            }), 400
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Initialize analytics engine
        analytics = ShopifyAnalytics(shopify_service, db_pool)
        
        # Get product analytics
        product_analytics = await analytics.get_product_analytics(
            user_id, start_date, end_date
        )
        
        return jsonify({
            "ok": True,
            "analytics": product_analytics.__dict__
        })
        
    except Exception as e:
        logger.error(f"Error getting product analytics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_analytics_bp.route('/api/shopify/analytics/inventory', methods=['POST'])
async def get_inventory_analytics():
    """Get inventory analytics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        
        if not all([user_id, start_date_str, end_date_str]):
            return jsonify({
                "ok": False,
                "error": "user_id, start_date, and end_date are required"
            }), 400
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Initialize analytics engine
        analytics = ShopifyAnalytics(shopify_service, db_pool)
        
        # Get inventory analytics
        inventory_analytics = await analytics.get_inventory_analytics(
            user_id, start_date, end_date
        )
        
        return jsonify({
            "ok": True,
            "analytics": inventory_analytics.__dict__
        })
        
    except Exception as e:
        logger.error(f"Error getting inventory analytics: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_analytics_bp.route('/api/shopify/analytics/report', methods=['POST'])
async def generate_analytics_report():
    """Generate comprehensive analytics report"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        include_forecast = data.get('include_forecast', True)
        
        if not all([user_id, start_date_str, end_date_str]):
            return jsonify({
                "ok": False,
                "error": "user_id, start_date, and end_date are required"
            }), 400
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Initialize analytics engine
        analytics = ShopifyAnalytics(shopify_service, db_pool)
        
        # Generate report
        result = await analytics.generate_analytics_report(
            user_id, start_date, end_date, include_forecast
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Error generating analytics report: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@shopify_analytics_bp.route('/api/shopify/analytics/forecast', methods=['POST'])
async def forecast_sales():
    """Generate sales forecast"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        start_date_str = data.get('start_date')
        end_date_str = data.get('end_date')
        forecast_days = int(data.get('forecast_days', 30))
        
        if not all([user_id, start_date_str, end_date_str]):
            return jsonify({
                "ok": False,
                "error": "user_id, start_date, and end_date are required"
            }), 400
        
        # Parse dates
        start_date = datetime.fromisoformat(start_date_str.replace('Z', '+00:00'))
        end_date = datetime.fromisoformat(end_date_str.replace('Z', '+00:00'))
        
        # Initialize analytics engine
        analytics = ShopifyAnalytics(shopify_service, db_pool)
        
        # Generate forecast
        forecast = await analytics.forecast_sales(
            user_id, start_date, end_date, forecast_days
        )
        
        return jsonify(forecast)
        
    except Exception as e:
        logger.error(f"Error forecasting sales: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

# =============================================================================
# Registration Function
# =============================================================================

def register_shopify_blueprints(app):
    """Register all Shopify blueprints with Flask app"""
    app.register_blueprint(shopify_bp, url_prefix='/api/shopify')
    app.register_blueprint(shopify_webhooks_bp, url_prefix='/api/shopify')
    app.register_blueprint(shopify_bulk_bp, url_prefix='/api/shopify')
    app.register_blueprint(shopify_apps_bp, url_prefix='/api/shopify')
    app.register_blueprint(shopify_analytics_bp, url_prefix='/api/shopify')
    
    logger.info("Shopify blueprints registered successfully")
    return True

# Export blueprints for direct registration
__all__ = [
    "register_shopify_blueprints",
    "shopify_bp",
    "shopify_webhooks_bp", 
    "shopify_bulk_bp",
    "shopify_apps_bp",
    "shopify_analytics_bp",
    "set_database_pool"
]