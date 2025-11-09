#!/usr/bin/env python3
"""
Enhanced HubSpot API Routes
Comprehensive API endpoints using the enhanced HubSpot service
"""

from flask import Blueprint, jsonify, request, g
import asyncio
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from enhanced_hubspot_service import EnhancedHubSpotService

# Create blueprint
hubspot_bp = Blueprint('enhanced_hubspot', __name__)
logger = logging.getLogger(__name__)

def async_route(f):
    """Decorator to run async functions in Flask routes"""
    import asyncio
    from functools import wraps
    
    @wraps(f)
    def wrapper(*args, **kwargs):
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(f(*args, **kwargs))
        finally:
            loop.close()
    
    return wrapper

def get_hubspot_service(user_id: str) -> EnhancedHubSpotService:
    """Get or create HubSpot service instance"""
    if not hasattr(g, 'hubspot_services'):
        g.hubspot_services = {}
    
    if user_id not in g.hubspot_services:
        g.hubspot_services[user_id] = EnhancedHubSpotService(user_id)
    
    return g.hubspot_services[user_id]

# Health Check
@hubspot_bp.route('/health', methods=['GET'])
@async_route
async def health_check():
    """Health check endpoint"""
    try:
        service = EnhancedHubSpotService("health_check")
        health_status = await service.health_check()
        
        return jsonify({
            "status": "healthy" if health_status.status == "active" else "unhealthy",
            "service": "HubSpot Enhanced API",
            "version": "2.0.0",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"HubSpot health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 503

# Contacts Management
@hubspot_bp.route('/contacts', methods=['GET'])
@async_route
async def get_contacts():
    """Get HubSpot contacts"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        after = request.args.get('after')
        properties = request.args.getlist('properties')
        archived = request.args.get('archived', 'false').lower() == 'true'
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_contacts(limit, after, properties, archived)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot contacts: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/contacts', methods=['POST'])
@async_route
async def create_contact():
    """Create a new HubSpot contact"""
    try:
        user_id = request.args.get('user_id')
        contact_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not contact_data:
            return jsonify({"error": "contact_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.create_contact(contact_data)
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to create HubSpot contact: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/contacts/<contact_id>', methods=['PATCH'])
@async_route
async def update_contact(contact_id: str):
    """Update an existing HubSpot contact"""
    try:
        user_id = request.args.get('user_id')
        contact_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not contact_data:
            return jsonify({"error": "contact_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.update_contact(contact_id, contact_data)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to update HubSpot contact {contact_id}: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/contacts/<contact_id>', methods=['DELETE'])
@async_route
async def delete_contact(contact_id: str):
    """Delete a HubSpot contact"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.delete_contact(contact_id)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to delete HubSpot contact {contact_id}: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/contacts/search', methods=['POST'])
@async_route
async def search_contacts():
    """Search HubSpot contacts"""
    try:
        user_id = request.args.get('user_id')
        search_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not search_data or 'query' not in search_data:
            return jsonify({"error": "search query is required"}), 400
        
        query = search_data['query']
        limit = search_data.get('limit', 10)
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.search_contacts(query, limit)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to search HubSpot contacts: {e}")
        return jsonify({"error": str(e)}), 500

# Companies Management
@hubspot_bp.route('/companies', methods=['GET'])
@async_route
async def get_companies():
    """Get HubSpot companies"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        after = request.args.get('after')
        properties = request.args.getlist('properties')
        archived = request.args.get('archived', 'false').lower() == 'true'
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_companies(limit, after, properties, archived)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot companies: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/companies', methods=['POST'])
@async_route
async def create_company():
    """Create a new HubSpot company"""
    try:
        user_id = request.args.get('user_id')
        company_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not company_data:
            return jsonify({"error": "company_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.create_company(company_data)
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to create HubSpot company: {e}")
        return jsonify({"error": str(e)}), 500

# Deals Management
@hubspot_bp.route('/deals', methods=['GET'])
@async_route
async def get_deals():
    """Get HubSpot deals"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        after = request.args.get('after')
        properties = request.args.getlist('properties')
        archived = request.args.get('archived', 'false').lower() == 'true'
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_deals(limit, after, properties, archived)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot deals: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/deals', methods=['POST'])
@async_route
async def create_deal():
    """Create a new HubSpot deal"""
    try:
        user_id = request.args.get('user_id')
        deal_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not deal_data:
            return jsonify({"error": "deal_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.create_deal(deal_data)
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to create HubSpot deal: {e}")
        return jsonify({"error": str(e)}), 500

# Engagements Management
@hubspot_bp.route('/engagements', methods=['GET'])
@async_route
async def get_engagements():
    """Get HubSpot engagements"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        after = request.args.get('after')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_engagements(limit, after)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot engagements: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/engagements/note', methods=['POST'])
@async_route
async def create_note():
    """Create a HubSpot note engagement"""
    try:
        user_id = request.args.get('user_id')
        note_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not note_data:
            return jsonify({"error": "note_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.create_note(note_data)
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to create HubSpot note: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/engagements/task', methods=['POST'])
@async_route
async def create_task():
    """Create a HubSpot task engagement"""
    try:
        user_id = request.args.get('user_id')
        task_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not task_data:
            return jsonify({"error": "task_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.create_task(task_data)
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to create HubSpot task: {e}")
        return jsonify({"error": str(e)}), 500

# Contact Lists Management
@hubspot_bp.route('/lists', methods=['GET'])
@async_route
async def get_contact_lists():
    """Get HubSpot contact lists"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_contact_lists(limit)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot contact lists: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/lists/<list_id>/memberships', methods=['GET'])
@async_route
async def get_list_memberships(list_id: str):
    """Get memberships for a specific contact list"""
    try:
        user_id = request.args.get('user_id')
        limit = int(request.args.get('limit', 100))
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_list_memberships(list_id, limit)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot list memberships: {e}")
        return jsonify({"error": str(e)}), 500

# Analytics and Reporting
@hubspot_bp.route('/analytics/contacts', methods=['GET'])
@async_route
async def get_contact_analytics():
    """Get contact analytics for a date range"""
    try:
        user_id = request.args.get('user_id')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not start_date or not end_date:
            return jsonify({"error": "start_date and end_date are required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_contact_analytics(start_date, end_date)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot contact analytics: {e}")
        return jsonify({"error": str(e)}), 500

# Webhooks Management
@hubspot_bp.route('/webhooks', methods=['GET'])
@async_route
async def get_webhooks():
    """Get all HubSpot webhooks"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.get_webhooks()
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to get HubSpot webhooks: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/webhooks', methods=['POST'])
@async_route
async def create_webhook():
    """Create a new HubSpot webhook"""
    try:
        user_id = request.args.get('user_id')
        webhook_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not webhook_data:
            return jsonify({"error": "webhook_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.create_webhook(webhook_data)
        
        if result["success"]:
            return jsonify(result), 201
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to create HubSpot webhook: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/webhooks/<webhook_id>', methods=['PATCH'])
@async_route
async def update_webhook(webhook_id: int):
    """Update an existing HubSpot webhook"""
    try:
        user_id = request.args.get('user_id')
        webhook_data = request.get_json()
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        if not webhook_data:
            return jsonify({"error": "webhook_data is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.update_webhook(webhook_id, webhook_data)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to update HubSpot webhook {webhook_id}: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/webhooks/<webhook_id>', methods=['DELETE'])
@async_route
async def delete_webhook(webhook_id: int):
    """Delete a HubSpot webhook"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        result = await service.delete_webhook(webhook_id)
        
        if result["success"]:
            return jsonify(result), 200
        else:
            return jsonify(result), 500
            
    except Exception as e:
        logger.error(f"Failed to delete HubSpot webhook {webhook_id}: {e}")
        return jsonify({"error": str(e)}), 500

# Service Metrics and Status
@hubspot_bp.route('/status', methods=['GET'])
@async_route
async def get_service_status():
    """Get service status and metrics"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        status = await service.get_status()
        metrics = await service.get_metrics()
        service_info = await service.get_service_info()
        
        return jsonify({
            "status": status.__dict__,
            "metrics": metrics.__dict__,
            "service_info": service_info
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to get HubSpot service status: {e}")
        return jsonify({"error": str(e)}), 500

@hubspot_bp.route('/metrics/reset', methods=['POST'])
@async_route
async def reset_metrics():
    """Reset service metrics"""
    try:
        user_id = request.args.get('user_id')
        
        if not user_id:
            return jsonify({"error": "user_id is required"}), 400
        
        service = get_hubspot_service(user_id)
        
        # Initialize service
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        init_success = await service.initialize(db_pool)
        
        if not init_success:
            return jsonify({
                "error": "Failed to initialize HubSpot service",
                "details": service.status.error_message
            }), 500
        
        await service.reset_metrics()
        
        return jsonify({
            "message": "Metrics reset successfully",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }), 200
        
    except Exception as e:
        logger.error(f"Failed to reset HubSpot metrics: {e}")
        return jsonify({"error": str(e)}), 500