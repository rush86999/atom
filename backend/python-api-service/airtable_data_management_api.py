"""
Airtable Data Management API Routes
Complete Airtable data management automation endpoints
"""

import os
import logging
import asyncio
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List, Union
from flask import Blueprint, request, jsonify, Response
from werkzeug.exceptions import BadRequest, NotFound, InternalServerError
from functools import wraps

# Import Airtable services
try:
    from airtable_enhanced_service import airtable_enhanced_service
    AIRTABLE_SERVICE_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Airtable service not available: {e}")
    AIRTABLE_SERVICE_AVAILABLE = False

try:
    from airtable_lancedb_ingestion_service import airtable_lancedb_service
    AIRTABLE_LANCEDB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Airtable LanceDB service not available: {e}")
    AIRTABLE_LANCEDB_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Create blueprint
airtable_data_management_bp = Blueprint('airtable_data_management', __name__)

# Error handling decorator
def handle_airtable_data_management_errors(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except BadRequest as e:
            logger.error(f"Bad request in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'bad_request'
            }), 400
        except NotFound as e:
            logger.error(f"Resource not found in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'not_found'
            }), 404
        except InternalServerError as e:
            logger.error(f"Internal server error in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'internal_server_error'
            }), 500
        except Exception as e:
            logger.error(f"Unexpected error in {f.__name__}: {e}")
            return jsonify({
                'ok': False,
                'error': str(e),
                'error_type': 'unexpected_error'
            }), 500
    return decorated_function

# User authentication decorator
def require_user_auth(f):
    @wraps(f)
    @handle_airtable_data_management_errors
    def decorated_function(*args, **kwargs):
        data = request.get_json() if request.method == 'POST' else request.args
        user_id = data.get('user_id')
        if not user_id:
            raise BadRequest('user_id is required')
        
        # Add user_id to kwargs
        kwargs['user_id'] = user_id
        
        return f(*args, **kwargs)
    return decorated_function

# Airtable API key validation decorator
def require_airtable_auth(f):
    @wraps(f)
    @handle_airtable_data_management_errors
    def decorated_function(*args, **kwargs):
        data = request.get_json() if request.method == 'POST' else request.args
        api_key = data.get('api_key') or os.getenv('AIRTABLE_API_KEY')
        
        if not api_key:
            raise BadRequest('Airtable API key is required')
        
        # Add auth to kwargs
        kwargs['api_key'] = api_key
        
        return f(*args, **kwargs)
    return decorated_function

# Health Check
@airtable_data_management_bp.route("/api/airtable/data-management/health", methods=["GET"])
@handle_airtable_data_management_errors
def health_check():
    """Airtable data management health check"""
    return jsonify({
        "ok": True,
        "service": "airtable_data_management",
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "services": {
            "airtable_service": AIRTABLE_SERVICE_AVAILABLE,
            "lancedb_service": AIRTABLE_LANCEDB_AVAILABLE
        }
    })

# Base Management
@airtable_data_management_bp.route("/api/airtable/data-management/bases/list", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def list_bases(user_id: str, api_key: str):
    """List Airtable bases"""
    try:
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service with provided API key
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bases = loop.run_until_complete(
            service.get_bases(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "bases": [base.to_dict() for base in bases],
            "total_bases": len(bases)
        })
        
    except Exception as e:
        logger.error(f"Error listing Airtable bases: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/bases/get", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def get_base(user_id: str, api_key: str):
    """Get Airtable base details"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        
        if not base_id:
            raise BadRequest('base_id is required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        base = loop.run_until_complete(
            service.get_base(base_id, user_id)
        )
        loop.close()
        
        if base:
            return jsonify({
                "ok": True,
                "base": base.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Base not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Airtable base: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Table Management
@airtable_data_management_bp.route("/api/airtable/data-management/tables/list", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def list_tables(user_id: str, api_key: str):
    """List Airtable tables from base"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        
        if not base_id:
            raise BadRequest('base_id is required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        tables = loop.run_until_complete(
            service.get_tables(base_id, user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "tables": [table.to_dict() for table in tables],
            "total_tables": len(tables),
            "base_id": base_id
        })
        
    except Exception as e:
        logger.error(f"Error listing Airtable tables: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/tables/get", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def get_table(user_id: str, api_key: str):
    """Get Airtable table details"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        
        if not base_id or not table_id:
            raise BadRequest('base_id and table_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        table = loop.run_until_complete(
            service.get_table(base_id, table_id, user_id)
        )
        loop.close()
        
        if table:
            return jsonify({
                "ok": True,
                "table": table.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Table not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Airtable table: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Record Management
@airtable_data_management_bp.route("/api/airtable/data-management/records/list", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def list_records(user_id: str, api_key: str):
    """List Airtable records from table"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        view_id = data.get('view_id')
        filter_by_formula = data.get('filter_by_formula')
        sort = data.get('sort')
        fields = data.get('fields')
        max_records = data.get('max_records', 100)
        page_size = data.get('page_size', 100)
        offset = data.get('offset')
        
        if not base_id or not table_id:
            raise BadRequest('base_id and table_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            service.get_records(
                base_id=base_id,
                table_id=table_id,
                view_id=view_id,
                filter_by_formula=filter_by_formula,
                sort=sort,
                fields=fields,
                max_records=max_records,
                page_size=page_size,
                offset=offset,
                user_id=user_id
            )
        )
        loop.close()
        
        records = result.get('records', [])
        offset_result = result.get('offset')
        error = result.get('error')
        
        if error:
            return jsonify({
                "ok": False,
                "error": error
            }), 500
        
        return jsonify({
            "ok": True,
            "records": [record.to_dict() for record in records],
            "total_records": len(records),
            "offset": offset_result,
            "filters": {
                "base_id": base_id,
                "table_id": table_id,
                "view_id": view_id,
                "filter_by_formula": filter_by_formula,
                "sort": sort,
                "fields": fields,
                "max_records": max_records,
                "page_size": page_size,
                "offset": offset
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Airtable records: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/records/get", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def get_record(user_id: str, api_key: str):
    """Get Airtable record details"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        record_id = data.get('record_id')
        
        if not base_id or not table_id or not record_id:
            raise BadRequest('base_id, table_id, and record_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        record = loop.run_until_complete(
            service.get_record(base_id, table_id, record_id, user_id)
        )
        loop.close()
        
        if record:
            return jsonify({
                "ok": True,
                "record": record.to_dict()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Record not found",
                "error_type": "not_found"
            }), 404
        
    except Exception as e:
        logger.error(f"Error getting Airtable record: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/records/create", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def create_record(user_id: str, api_key: str):
    """Create Airtable record"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        fields = data.get('fields', {})
        
        if not base_id or not table_id:
            raise BadRequest('base_id and table_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        record = loop.run_until_complete(
            service.create_record(
                base_id=base_id,
                table_id=table_id,
                fields=fields,
                user_id=user_id
            )
        )
        loop.close()
        
        if record:
            return jsonify({
                "ok": True,
                "record": record.to_dict(),
                "message": "Record created successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to create record",
                "error_type": "create_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error creating Airtable record: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/records/update", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def update_record(user_id: str, api_key: str):
    """Update Airtable record"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        record_id = data.get('record_id')
        fields = data.get('fields', {})
        
        if not base_id or not table_id or not record_id:
            raise BadRequest('base_id, table_id, and record_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        record = loop.run_until_complete(
            service.update_record(
                base_id=base_id,
                table_id=table_id,
                record_id=record_id,
                fields=fields,
                user_id=user_id
            )
        )
        loop.close()
        
        if record:
            return jsonify({
                "ok": True,
                "record": record.to_dict(),
                "message": "Record updated successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to update record",
                "error_type": "update_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error updating Airtable record: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/records/delete", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def delete_record(user_id: str, api_key: str):
    """Delete Airtable record"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        record_id = data.get('record_id')
        
        if not base_id or not table_id or not record_id:
            raise BadRequest('base_id, table_id, and record_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            service.delete_record(base_id, table_id, record_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Record deleted successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete record",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Airtable record: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Field Management
@airtable_data_management_bp.route("/api/airtable/data-management/fields/list", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def list_fields(user_id: str, api_key: str):
    """List Airtable fields from table"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        
        if not base_id or not table_id:
            raise BadRequest('base_id and table_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        fields = loop.run_until_complete(
            service.get_fields(base_id, table_id, user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "fields": [field.to_dict() for field in fields],
            "total_fields": len(fields),
            "table_id": table_id
        })
        
    except Exception as e:
        logger.error(f"Error listing Airtable fields: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# View Management
@airtable_data_management_bp.route("/api/airtable/data-management/views/list", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def list_views(user_id: str, api_key: str):
    """List Airtable views from table"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        
        if not base_id or not table_id:
            raise BadRequest('base_id and table_id are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        views = loop.run_until_complete(
            service.get_views(base_id, table_id, user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "views": [view.to_dict() for view in views],
            "total_views": len(views),
            "table_id": table_id
        })
        
    except Exception as e:
        logger.error(f"Error listing Airtable views: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Search Operations
@airtable_data_management_bp.route("/api/airtable/data-management/search/records", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def search_records(user_id: str, api_key: str):
    """Search Airtable records"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        table_id = data.get('table_id')
        search_query = data.get('search_query')
        view_id = data.get('view_id')
        fields = data.get('fields')
        max_records = data.get('max_records', 100)
        
        if not base_id or not table_id or not search_query:
            raise BadRequest('base_id, table_id, and search_query are required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            service.search_records(
                base_id=base_id,
                table_id=table_id,
                search_query=search_query,
                view_id=view_id,
                fields=fields,
                max_records=max_records,
                user_id=user_id
            )
        )
        loop.close()
        
        records = result.get('records', [])
        offset_result = result.get('offset')
        error = result.get('error')
        
        if error:
            return jsonify({
                "ok": False,
                "error": error
            }), 500
        
        return jsonify({
            "ok": True,
            "records": [record.to_dict() for record in records],
            "count": len(records),
            "offset": offset_result,
            "search_filters": {
                "base_id": base_id,
                "table_id": table_id,
                "search_query": search_query,
                "view_id": view_id,
                "fields": fields,
                "max_records": max_records
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Airtable records: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Webhook Management
@airtable_data_management_bp.route("/api/airtable/data-management/webhooks/list", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
@require_airtable_auth
def list_webhooks(user_id: str, api_key: str):
    """List Airtable webhooks from base"""
    try:
        data = request.get_json()
        base_id = data.get('base_id')
        
        if not base_id:
            raise BadRequest('base_id is required')
        
        if not AIRTABLE_SERVICE_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable service not available"
            }), 503
        
        # Initialize service
        service = __import__('airtable_enhanced_service', fromlist=['AirtableEnhancedService']).AirtableEnhancedService(api_key)
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        webhooks = loop.run_until_complete(
            service.get_webhooks(base_id, user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "webhooks": [webhook.to_dict() for webhook in webhooks],
            "total_webhooks": len(webhooks),
            "base_id": base_id
        })
        
    except Exception as e:
        logger.error(f"Error listing Airtable webhooks: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Memory Management
@airtable_data_management_bp.route("/api/airtable/data-management/memory/settings", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def get_memory_settings(user_id: str):
    """Get Airtable memory settings for user"""
    try:
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        settings = loop.run_until_complete(
            airtable_lancedb_service.get_user_settings(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "settings": {
                "user_id": settings.user_id,
                "ingestion_enabled": settings.ingestion_enabled,
                "sync_frequency": settings.sync_frequency,
                "data_retention_days": settings.data_retention_days,
                "include_bases": settings.include_bases or [],
                "exclude_bases": settings.exclude_bases or [],
                "include_archived_bases": settings.include_archived_bases,
                "include_tables": settings.include_tables,
                "include_records": settings.include_records,
                "include_fields": settings.include_fields,
                "include_views": settings.include_views,
                "include_attachments": settings.include_attachments,
                "include_webhooks": settings.include_webhooks,
                "max_records_per_sync": settings.max_records_per_sync,
                "max_table_records_per_sync": settings.max_table_records_per_sync,
                "sync_deleted_records": settings.sync_deleted_records,
                "sync_record_attachments": settings.sync_record_attachments,
                "index_record_content": settings.index_record_content,
                "search_enabled": settings.search_enabled,
                "semantic_search_enabled": settings.semantic_search_enabled,
                "metadata_extraction_enabled": settings.metadata_extraction_enabled,
                "base_tracking_enabled": settings.base_tracking_enabled,
                "table_analysis_enabled": settings.table_analysis_enabled,
                "field_analysis_enabled": settings.field_analysis_enabled,
                "last_sync_timestamp": settings.last_sync_timestamp,
                "next_sync_timestamp": settings.next_sync_timestamp,
                "sync_in_progress": settings.sync_in_progress,
                "error_message": settings.error_message,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Airtable memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/settings", methods=["PUT"])
@handle_airtable_data_management_errors
@require_user_auth
def save_memory_settings(user_id: str):
    """Save Airtable memory settings for user"""
    try:
        data = request.get_json()
        
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Validate settings
        valid_frequencies = ["real-time", "hourly", "daily", "weekly", "manual"]
        sync_frequency = data.get('sync_frequency', 'hourly')
        if sync_frequency not in valid_frequencies:
            return jsonify({
                "ok": False,
                "error": f"Invalid sync frequency. Must be one of: {valid_frequencies}",
                "error_type": "validation_error"
            }), 400
        
        # Create settings object
        settings_class = __import__('airtable_lancedb_ingestion_service', fromlist=['AirtableMemorySettings']).AirtableMemorySettings
        settings = settings_class(
            user_id=user_id,
            ingestion_enabled=data.get('ingestion_enabled', True),
            sync_frequency=sync_frequency,
            data_retention_days=data.get('data_retention_days', 365),
            include_bases=data.get('include_bases', []),
            exclude_bases=data.get('exclude_bases', []),
            include_archived_bases=data.get('include_archived_bases', False),
            include_tables=data.get('include_tables', True),
            include_records=data.get('include_records', True),
            include_fields=data.get('include_fields', True),
            include_views=data.get('include_views', True),
            include_attachments=data.get('include_attachments', True),
            include_webhooks=data.get('include_webhooks', True),
            max_records_per_sync=data.get('max_records_per_sync', 1000),
            max_table_records_per_sync=data.get('max_table_records_per_sync', 500),
            sync_deleted_records=data.get('sync_deleted_records', True),
            sync_record_attachments=data.get('sync_record_attachments', True),
            index_record_content=data.get('index_record_content', True),
            search_enabled=data.get('search_enabled', True),
            semantic_search_enabled=data.get('semantic_search_enabled', True),
            metadata_extraction_enabled=data.get('metadata_extraction_enabled', True),
            base_tracking_enabled=data.get('base_tracking_enabled', True),
            table_analysis_enabled=data.get('table_analysis_enabled', True),
            field_analysis_enabled=data.get('field_analysis_enabled', True)
        )
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            airtable_lancedb_service.save_user_settings(settings)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Airtable memory settings saved successfully",
                "settings": {
                    "user_id": settings.user_id,
                    "ingestion_enabled": settings.ingestion_enabled,
                    "sync_frequency": settings.sync_frequency,
                    "updated_at": settings.updated_at
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to save Airtable memory settings",
                "error_type": "save_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error saving Airtable memory settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/ingest", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def start_ingestion(user_id: str):
    """Start Airtable data ingestion"""
    try:
        data = request.get_json()
        api_key = data.get('api_key') or os.getenv('AIRTABLE_API_KEY')
        base_ids = data.get('base_ids', [])
        force_sync = data.get('force_sync', False)
        
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            airtable_lancedb_service.ingest_airtable_data(
                user_id=user_id,
                api_key=api_key,
                force_sync=force_sync,
                base_ids=base_ids
            )
        )
        loop.close()
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "ingestion_result": {
                    "bases_ingested": result.get('bases_ingested', 0),
                    "tables_ingested": result.get('tables_ingested', 0),
                    "records_ingested": result.get('records_ingested', 0),
                    "fields_ingested": result.get('fields_ingested', 0),
                    "views_ingested": result.get('views_ingested', 0),
                    "webhooks_ingested": result.get('webhooks_ingested', 0),
                    "attachments_ingested": result.get('attachments_ingested', 0),
                    "total_size_mb": result.get('total_size_mb', 0),
                    "batch_id": result.get('batch_id'),
                    "next_sync": result.get('next_sync'),
                    "sync_frequency": result.get('sync_frequency')
                },
                "message": "Airtable data ingestion completed successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown ingestion error'),
                "error_type": result.get('error_type', 'ingestion_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting Airtable ingestion: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/status", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def get_memory_status(user_id: str):
    """Get Airtable memory synchronization status"""
    try:
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        status = loop.run_until_complete(
            airtable_lancedb_service.get_sync_status(user_id)
        )
        loop.close()
        
        if status.get('error'):
            return jsonify({
                "ok": False,
                "error": status.get('error'),
                "error_type": status.get('error_type', 'status_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "memory_status": status
        })
        
    except Exception as e:
        logger.error(f"Error getting Airtable memory status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/search/bases", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def search_memory_bases(user_id: str):
    """Search Airtable bases in memory"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        sharing = data.get('sharing', None)
        limit = data.get('limit', 50)
        
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bases = loop.run_until_complete(
            airtable_lancedb_service.search_airtable_bases(
                user_id=user_id,
                query=query,
                sharing=sharing,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "bases": bases,
            "count": len(bases),
            "search_filters": {
                "query": query,
                "sharing": sharing,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Airtable memory bases: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/search/records", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def search_memory_records(user_id: str):
    """Search Airtable records in memory"""
    try:
        data = request.get_json()
        query = data.get('query', '')
        base_id = data.get('base_id', None)
        table_id = data.get('table_id', None)
        field_type = data.get('field_type', None)
        limit = data.get('limit', 50)
        
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        records = loop.run_until_complete(
            airtable_lancedb_service.search_airtable_records(
                user_id=user_id,
                query=query,
                base_id=base_id,
                table_id=table_id,
                field_type=field_type,
                limit=limit
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "records": records,
            "count": len(records),
            "search_filters": {
                "query": query,
                "base_id": base_id,
                "table_id": table_id,
                "field_type": field_type,
                "limit": limit
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Airtable memory records: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/ingestion-stats", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def get_ingestion_stats(user_id: str):
    """Get Airtable ingestion statistics"""
    try:
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(
            airtable_lancedb_service.get_ingestion_stats(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "ingestion_stats": {
                "user_id": stats.user_id,
                "total_bases_ingested": stats.total_bases_ingested,
                "total_tables_ingested": stats.total_tables_ingested,
                "total_records_ingested": stats.total_records_ingested,
                "total_fields_ingested": stats.total_fields_ingested,
                "total_views_ingested": stats.total_views_ingested,
                "total_webhooks_ingested": stats.total_webhooks_ingested,
                "total_attachments_ingested": stats.total_attachments_ingested,
                "last_ingestion_timestamp": stats.last_ingestion_timestamp,
                "total_size_mb": stats.total_size_mb,
                "failed_ingestions": stats.failed_ingestions,
                "last_error_message": stats.last_error_message,
                "avg_records_per_table": stats.avg_records_per_table,
                "avg_fields_per_table": stats.avg_fields_per_table,
                "avg_processing_time_ms": stats.avg_processing_time_ms,
                "created_at": stats.created_at,
                "updated_at": stats.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Airtable ingestion stats: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@airtable_data_management_bp.route("/api/airtable/data-management/memory/delete", methods=["POST"])
@handle_airtable_data_management_errors
@require_user_auth
def delete_user_data(user_id: str):
    """Delete all Airtable data for user"""
    try:
        data = request.get_json()
        confirm = data.get('confirm', False)
        
        if not AIRTABLE_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Airtable LanceDB service not available"
            }), 503
        
        if not confirm:
            return jsonify({
                "ok": False,
                "error": "Confirmation required to delete Airtable data",
                "error_type": "confirmation_required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            airtable_lancedb_service.delete_user_data(user_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "All Airtable data deleted successfully",
                "deleted_at": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete Airtable data",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Airtable user data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility Endpoints
@airtable_data_management_bp.route("/api/airtable/data-management/service-info", methods=["GET"])
@handle_airtable_data_management_errors
def get_service_info():
    """Get service information"""
    try:
        if AIRTABLE_SERVICE_AVAILABLE:
            service_info = airtable_enhanced_service.get_service_info()
        else:
            service_info = {
                "name": "Enhanced Airtable Service",
                "version": "1.0.0",
                "error": "Airtable service not available"
            }
        
        return jsonify({
            "ok": True,
            "service_info": service_info,
            "lancedb_available": AIRTABLE_LANCEDB_AVAILABLE,
            "airtable_service_available": AIRTABLE_SERVICE_AVAILABLE
        })
        
    except Exception as e:
        logger.error(f"Error getting Airtable service info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Export components
__all__ = [
    'airtable_data_management_bp'
]