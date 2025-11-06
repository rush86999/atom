"""
👥 Zoom Multi-Account API Routes
Enterprise-grade multi-account management endpoints
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify

from zoom_multi_account_manager import ZoomMultiAccountManager, AccountType, AccountStatus

logger = logging.getLogger(__name__)

# Create blueprint
zoom_multi_account_bp = Blueprint("zoom_multi_account", __name__)

# Global account manager
account_manager: Optional[ZoomMultiAccountManager] = None

def init_zoom_multi_account_manager(db_pool):
    """Initialize Zoom multi-account manager"""
    global account_manager
    account_manager = ZoomMultiAccountManager(db_pool)
    return account_manager

def format_response(data: Any, endpoint: str, status: str = 'success') -> Dict[str, Any]:
    """Format API response"""
    return {
        'ok': status == 'success',
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_multi_account_api'
    }

def format_error_response(error: str, endpoint: str, status_code: int = 500) -> tuple:
    """Format error response"""
    error_response = {
        'ok': False,
        'error': {
            'code': 'ACCOUNT_ERROR',
            'message': error,
            'endpoint': endpoint
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_multi_account_api'
    }
    return jsonify(error_response), status_code

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> tuple:
    """Validate required fields in request data"""
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    
    if missing_fields:
        error_msg = f"Missing required fields: {', '.join(missing_fields)}"
        return False, error_msg
    
    return True, None

def get_client_info() -> Dict[str, str]:
    """Get client information for security"""
    return {
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'ip_address': request.environ.get('REMOTE_ADDR', request.headers.get('X-Forwarded-For', 'Unknown')),
        'referer': request.headers.get('Referer', 'Unknown'),
        'origin': request.headers.get('Origin', 'Unknown'),
        'accept_language': request.headers.get('Accept-Language', 'Unknown')
    }

# === ACCOUNT MANAGEMENT ENDPOINTS ===

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/list", methods=["POST"])
async def list_accounts():
    """List all accounts for a user"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/accounts/list', 400)
        
        user_id = request_data['user_id']
        include_inactive = request_data.get('include_inactive', False)
        
        # Get accounts for user
        accounts = await account_manager.get_accounts(user_id, include_inactive)
        
        # Convert to dict format
        accounts_data = [
            {
                'account_id': account.account_id,
                'user_id': account.user_id,
                'account_name': account.account_name,
                'account_email': account.account_email,
                'account_type': account.account_type.value,
                'account_status': account.account_status.value,
                'zoom_account_id': account.zoom_account_id,
                'zoom_user_id': account.zoom_user_id,
                'zoom_user_type': account.zoom_user_type,
                'zoom_role_name': account.zoom_role_name,
                'is_primary': account.is_primary,
                'is_default': account.is_default,
                'oauth_token_id': account.oauth_token_id,
                'created_at': account.created_at.isoformat(),
                'last_used_at': account.last_used_at.isoformat() if account.last_used_at else None,
                'access_count': account.access_count,
                'permissions': account.permissions,
                'metadata': account.metadata
            }
            for account in accounts
        ]
        
        response_data = {
            'user_id': user_id,
            'accounts': accounts_data,
            'total_count': len(accounts_data),
            'active_count': len([a for a in accounts_data if a['account_status'] == 'active']),
            'primary_count': len([a for a in accounts_data if a['is_primary']]),
            'include_inactive': include_inactive
        }
        
        return format_response(response_data, '/accounts/list')
        
    except Exception as e:
        logger.error(f"Failed to list accounts: {e}")
        return format_error_response(str(e), '/accounts/list', 500)

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/add", methods=["POST"])
async def add_account():
    """Add a new Zoom account"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        required_fields = [
            'user_id', 'account_name', 'account_email', 'account_type',
            'zoom_account_id', 'zoom_user_id', 'zoom_user_type', 'zoom_role_name', 'oauth_token_id'
        ]
        is_valid, error = validate_required_fields(request_data, required_fields)
        if not is_valid:
            return format_error_response(error, '/accounts/add', 400)
        
        # Parse account type
        account_type = AccountType(request_data['account_type'])
        
        # Add account
        account_id = await account_manager.add_account(
            user_id=request_data['user_id'],
            account_name=request_data['account_name'],
            account_email=request_data['account_email'],
            account_type=account_type,
            zoom_account_id=request_data['zoom_account_id'],
            zoom_user_id=request_data['zoom_user_id'],
            zoom_user_type=request_data['zoom_user_type'],
            zoom_role_name=request_data['zoom_role_name'],
            oauth_token_id=request_data['oauth_token_id'],
            is_primary=request_data.get('is_primary', False),
            permissions=request_data.get('permissions', []),
            metadata=request_data.get('metadata', {})
        )
        
        if account_id:
            response_data = {
                'success': True,
                'account_id': account_id,
                'user_id': request_data['user_id'],
                'account_name': request_data['account_name'],
                'account_type': account_type.value,
                'created_at': datetime.now(timezone.utc).isoformat()
            }
            
            return format_response(response_data, '/accounts/add')
        else:
            return format_error_response('Failed to add account', '/accounts/add', 500)
        
    except ValueError as e:
        return format_error_response(f'Invalid account type: {e}', '/accounts/add', 400)
    except Exception as e:
        logger.error(f"Failed to add account: {e}")
        return format_error_response(str(e), '/accounts/add', 500)

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/switch", methods=["POST"])
async def switch_account():
    """Switch to a different account"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'target_account_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        if not is_valid:
            return format_error_response(error, '/accounts/switch', 400)
        
        # Create switch request
        from zoom_multi_account_manager import AccountSwitchRequest
        switch_request = AccountSwitchRequest(
            user_id=request_data['user_id'],
            target_account_id=request_data['target_account_id'],
            reason=request_data.get('reason'),
            metadata=request_data.get('metadata', {})
        )
        
        # Get client information
        client_info = get_client_info()
        
        # Switch account
        switch_result = await account_manager.switch_account(switch_request, client_info)
        
        response_data = {
            'success': switch_result.success,
            'user_id': switch_result.user_id,
            'previous_account_id': switch_result.previous_account_id,
            'current_account_id': switch_result.current_account_id,
            'switch_time': switch_result.switch_time.isoformat(),
            'reason': switch_result.reason,
            'client_info': client_info
        }
        
        if not switch_result.success:
            response_data['error'] = switch_result.error
            return format_response(response_data, '/accounts/switch')
        
        return format_response(response_data, '/accounts/switch')
        
    except Exception as e:
        logger.error(f"Failed to switch account: {e}")
        return format_error_response(str(e), '/accounts/switch', 500)

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/default", methods=["POST"])
async def get_default_account():
    """Get default account for user"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/accounts/default', 400)
        
        user_id = request_data['user_id']
        
        # Get default account
        default_account = await account_manager.get_default_account(user_id)
        
        if default_account:
            response_data = {
                'account_id': default_account.account_id,
                'user_id': default_account.user_id,
                'account_name': default_account.account_name,
                'account_email': default_account.account_email,
                'account_type': default_account.account_type.value,
                'account_status': default_account.account_status.value,
                'zoom_account_id': default_account.zoom_account_id,
                'zoom_user_id': default_account.zoom_user_id,
                'zoom_user_type': default_account.zoom_user_type,
                'zoom_role_name': default_account.zoom_role_name,
                'is_primary': default_account.is_primary,
                'is_default': default_account.is_default,
                'created_at': default_account.created_at.isoformat(),
                'last_used_at': default_account.last_used_at.isoformat() if default_account.last_used_at else None,
                'access_count': default_account.access_count,
                'permissions': default_account.permissions,
                'metadata': default_account.metadata
            }
            
            return format_response(response_data, '/accounts/default')
        else:
            return format_error_response('No default account found', '/accounts/default', 404)
        
    except Exception as e:
        logger.error(f"Failed to get default account: {e}")
        return format_error_response(str(e), '/accounts/default', 500)

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/update", methods=["POST"])
async def update_account():
    """Update account information"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['account_id'])
        if not is_valid:
            return format_error_response(error, '/accounts/update', 400)
        
        account_id = request_data['account_id']
        updates = request_data.get('updates', {})
        
        if not updates:
            return format_error_response('No updates provided', '/accounts/update', 400)
        
        # Update account
        success = await account_manager.update_account(account_id, updates)
        
        if success:
            response_data = {
                'success': True,
                'account_id': account_id,
                'updates_applied': updates,
                'updated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return format_response(response_data, '/accounts/update')
        else:
            return format_error_response('Failed to update account', '/accounts/update', 500)
        
    except Exception as e:
        logger.error(f"Failed to update account: {e}")
        return format_error_response(str(e), '/accounts/update', 500)

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/remove", methods=["POST"])
async def remove_account():
    """Remove an account"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['account_id', 'user_id'])
        if not is_valid:
            return format_error_response(error, '/accounts/remove', 400)
        
        account_id = request_data['account_id']
        user_id = request_data['user_id']
        
        # Remove account
        success = await account_manager.remove_account(account_id, user_id)
        
        if success:
            response_data = {
                'success': True,
                'account_id': account_id,
                'user_id': user_id,
                'removed_at': datetime.now(timezone.utc).isoformat()
            }
            
            return format_response(response_data, '/accounts/remove')
        else:
            return format_error_response('Cannot remove primary account or account not found', '/accounts/remove', 400)
        
    except Exception as e:
        logger.error(f"Failed to remove account: {e}")
        return format_error_response(str(e), '/accounts/remove', 500)

# === PERMISSIONS ENDPOINTS ===

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/permissions/set", methods=["POST"])
async def set_account_permissions():
    """Set permissions for an account"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        required_fields = ['account_id', 'permissions']
        is_valid, error = validate_required_fields(request_data, required_fields)
        if not is_valid:
            return format_error_response(error, '/accounts/permissions/set', 400)
        
        account_id = request_data['account_id']
        permissions = request_data['permissions']
        
        # Set permissions
        success = await account_manager.set_account_permissions(account_id, permissions)
        
        if success:
            response_data = {
                'success': True,
                'account_id': account_id,
                'permissions': permissions,
                'set_at': datetime.now(timezone.utc).isoformat()
            }
            
            return format_response(response_data, '/accounts/permissions/set')
        else:
            return format_error_response('Failed to set permissions', '/accounts/permissions/set', 500)
        
    except Exception as e:
        logger.error(f"Failed to set account permissions: {e}")
        return format_error_response(str(e), '/accounts/permissions/set', 500)

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/permissions/check", methods=["POST"])
async def check_account_permission():
    """Check if account has specific permission"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        required_fields = ['account_id', 'permission']
        is_valid, error = validate_required_fields(request_data, required_fields)
        if not is_valid:
            return format_error_response(error, '/accounts/permissions/check', 400)
        
        account_id = request_data['account_id']
        permission = request_data['permission']
        
        # Check permission
        has_permission = await account_manager.check_account_permission(account_id, permission)
        
        response_data = {
            'has_permission': has_permission,
            'account_id': account_id,
            'permission': permission,
            'checked_at': datetime.now(timezone.utc).isoformat()
        }
        
        return format_response(response_data, '/accounts/permissions/check')
        
    except Exception as e:
        logger.error(f"Failed to check account permission: {e}")
        return format_error_response(str(e), '/accounts/permissions/check', 500)

# === HISTORY ENDPOINTS ===

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/history", methods=["POST"])
async def get_account_switch_history():
    """Get account switch history"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/accounts/history', 400)
        
        user_id = request_data['user_id']
        limit = request_data.get('limit', 50)
        from_date = request_data.get('from_date')
        to_date = request_data.get('to_date')
        
        # Parse dates if provided
        if from_date:
            from_date = datetime.fromisoformat(from_date.replace('Z', '+00:00'))
        if to_date:
            to_date = datetime.fromisoformat(to_date.replace('Z', '+00:00'))
        
        # Get switch history
        history = await account_manager.get_account_switch_history(user_id, limit, from_date, to_date)
        
        response_data = {
            'user_id': user_id,
            'history': history,
            'total_count': len(history),
            'limit': limit,
            'from_date': from_date.isoformat() if from_date else None,
            'to_date': to_date.isoformat() if to_date else None
        }
        
        return format_response(response_data, '/accounts/history')
        
    except ValueError as e:
        return format_error_response(f'Invalid date format: {e}', '/accounts/history', 400)
    except Exception as e:
        logger.error(f"Failed to get account switch history: {e}")
        return format_error_response(str(e), '/accounts/history', 500)

# === STATISTICS ENDPOINTS ===

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/statistics", methods=["POST"])
async def get_account_statistics():
    """Get account statistics for user"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/accounts/statistics', 400)
        
        user_id = request_data['user_id']
        
        # Get statistics
        stats = await account_manager.get_account_statistics(user_id)
        
        if stats:
            response_data = {
                'user_id': user_id,
                'statistics': stats,
                'generated_at': datetime.now(timezone.utc).isoformat()
            }
            
            return format_response(response_data, '/accounts/statistics')
        else:
            return format_error_response('No statistics found', '/accounts/statistics', 404)
        
    except Exception as e:
        logger.error(f"Failed to get account statistics: {e}")
        return format_error_response(str(e), '/accounts/statistics', 500)

# === CLEANUP ENDPOINTS ===

@zoom_multi_account_bp.route("/api/integrations/zoom/accounts/cleanup", methods=["POST"])
async def cleanup_inactive_accounts():
    """Clean up inactive accounts"""
    try:
        request_data = request.get_json()
        days = request_data.get('days', 90)
        
        # Clean up inactive accounts
        cleaned_count = await account_manager.cleanup_inactive_accounts(days)
        
        response_data = {
            'success': True,
            'cleaned_accounts': cleaned_count,
            'days_threshold': days,
            'cleanup_time': datetime.now(timezone.utc).isoformat()
        }
        
        return format_response(response_data, '/accounts/cleanup')
        
    except Exception as e:
        logger.error(f"Failed to cleanup inactive accounts: {e}")
        return format_error_response(str(e), '/accounts/cleanup', 500)

# === ERROR HANDLING ===

@zoom_multi_account_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return format_error_response('Bad Request', 'global', 400)

@zoom_multi_account_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized"""
    return format_error_response('Unauthorized', 'global', 401)

@zoom_multi_account_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden"""
    return format_error_response('Forbidden', 'global', 403)

@zoom_multi_account_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return format_error_response('Not Found', 'global', 404)

@zoom_multi_account_bp.errorhandler(429)
def rate_limited(error):
    """Handle 429 Too Many Requests"""
    return format_error_response('Rate Limit Exceeded', 'global', 429)

@zoom_multi_account_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error"""
    logger.error(f"Internal server error: {error}")
    return format_error_response('Internal Server Error', 'global', 500)