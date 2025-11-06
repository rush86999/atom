"""
🔐 Zoom Speech-to-Text BYOK API Routes
Bring Your Own Key management system for speech-to-text services
"""

import os
import json
import logging
import asyncio
import base64
import secrets
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from flask import Blueprint, request, jsonify, abort, current_app

from zoom_speech_byok_system import (
    ZoomSpeechBYOKManager, 
    BYOKKeyRequest, 
    ProviderType, 
    KeyStatus
)

logger = logging.getLogger(__name__)

# Create blueprint
zoom_speech_byok_bp = Blueprint("zoom_speech_byok", __name__)

# Global BYOK manager
byok_manager: Optional[ZoomSpeechBYOKManager] = None

def init_zoom_speech_byok_manager(db_pool: asyncpg.Pool, encryption_key: str = None):
    """Initialize Zoom Speech BYOK manager"""
    global byok_manager
    
    try:
        byok_manager = ZoomSpeechBYOKManager(db_pool, encryption_key)
        
        # Start processing
        asyncio.create_task(byok_manager.start_processing())
        
        logger.info("Zoom Speech BYOK manager initialized successfully")
        return byok_manager
        
    except Exception as e:
        logger.error(f"Failed to initialize Zoom Speech BYOK manager: {e}")
        raise

def format_response(data: Any, endpoint: str, status: str = 'success') -> Dict[str, Any]:
    """Format API response"""
    return {
        'ok': status == 'success',
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_speech_byok_api'
    }

def format_error_response(error: str, endpoint: str, status_code: int = 500) -> tuple:
    """Format error response"""
    error_response = {
        'ok': False,
        'error': {
            'code': 'BYOK_ERROR',
            'message': error,
            'endpoint': endpoint
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_speech_byok_api'
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

def require_admin(func):
    """Decorator to require admin privileges"""
    def wrapper(*args, **kwargs):
        # Check for admin token or session
        admin_token = request.headers.get('X-Admin-Token')
        if not admin_token or admin_token != os.getenv('BYOK_ADMIN_TOKEN', 'admin-secret'):
            return format_error_response('Admin privileges required', request.endpoint, 403)
        return func(*args, **kwargs)
    wrapper.__name__ = func.__name__
    return wrapper

# === KEY MANAGEMENT ENDPOINTS ===

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/add", methods=["POST"])
@require_admin
async def add_provider_key():
    """Add a new provider key"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['provider', 'key_name', 'api_key', 'account_id', 'account_name']
        )
        if not is_valid:
            return format_error_response(error, '/speech/byok/keys/add', 400)
        
        # Create key request
        key_request = BYOKKeyRequest(
            provider=request_data['provider'],
            key_name=request_data['key_name'],
            api_key=request_data['api_key'],
            account_id=request_data['account_id'],
            account_name=request_data['account_name'],
            billing_id=request_data.get('billing_id'),
            key_permissions=request_data.get('key_permissions', []),
            key_expires_at=datetime.fromisoformat(request_data['key_expires_at']) if request_data.get('key_expires_at') else None,
            rotation_frequency_days=request_data.get('rotation_frequency_days', 90),
            usage_quota=request_data.get('usage_quota'),
            usage_quota_period=request_data.get('usage_quota_period', 'monthly'),
            rate_limit_per_minute=request_data.get('rate_limit_per_minute', 1000),
            metadata=request_data.get('metadata', {})
        )
        
        # Add key
        if byok_manager:
            client_info = get_client_info()
            provider_key = await byok_manager.add_provider_key(
                key_request,
                client_info['user_id'] if 'user_id' in client_info else 'admin',
                client_info['ip_address'],
                client_info['user_agent']
            )
            
            if provider_key:
                response_data = {
                    'key_id': provider_key.key_id,
                    'provider': provider_key.provider.value,
                    'key_name': provider_key.key_name,
                    'account_name': provider_key.account_name,
                    'key_status': provider_key.key_status.value,
                    'rotation_frequency_days': provider_key.rotation_frequency_days,
                    'usage_quota': provider_key.usage_quota,
                    'usage_quota_period': provider_key.usage_quota_period,
                    'rate_limit_per_minute': provider_key.rate_limit_per_minute,
                    'created_at': provider_key.created_at.isoformat(),
                    'client_info': client_info
                }
                
                return format_response(response_data, '/speech/byok/keys/add')
            else:
                return format_error_response('Failed to add provider key', '/speech/byok/keys/add', 500)
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/keys/add', 503)
        
    except Exception as e:
        logger.error(f"Failed to add provider key: {e}")
        return format_error_response(str(e), '/speech/byok/keys/add', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/list", methods=["GET"])
@require_admin
async def list_provider_keys():
    """List all provider keys"""
    try:
        provider = request.args.get('provider')
        status = request.args.get('status')
        account_id = request.args.get('account_id')
        
        if byok_manager:
            keys = byok_manager.get_all_keys()
            
            # Filter results
            if provider:
                try:
                    provider_type = ProviderType(provider)
                    keys = [key for key in keys if key.provider == provider_type]
                except ValueError:
                    return format_error_response(f'Invalid provider: {provider}', '/speech/byok/keys/list', 400)
            
            if status:
                try:
                    key_status = KeyStatus(status)
                    keys = [key for key in keys if key.key_status == key_status]
                except ValueError:
                    return format_error_response(f'Invalid status: {status}', '/speech/byok/keys/list', 400)
            
            if account_id:
                keys = [key for key in keys if key.account_id == account_id]
            
            # Format response
            keys_data = []
            for key in keys:
                keys_data.append({
                    'key_id': key.key_id,
                    'provider': key.provider.value,
                    'key_name': key.key_name,
                    'account_name': key.account_name,
                    'key_status': key.key_status.value,
                    'rotation_status': key.rotation_status.value,
                    'key_usage_count': key.key_usage_count,
                    'key_last_used': key.key_last_used.isoformat() if key.key_last_used else None,
                    'key_expires_at': key.key_expires_at.isoformat() if key.key_expires_at else None,
                    'rotation_frequency_days': key.rotation_frequency_days,
                    'usage_quota': key.usage_quota,
                    'rate_limit_per_minute': key.rate_limit_per_minute,
                    'created_at': key.created_at.isoformat(),
                    'updated_at': key.updated_at.isoformat()
                })
            
            response_data = {
                'keys': keys_data,
                'total_count': len(keys_data),
                'provider_filter': provider,
                'status_filter': status,
                'account_id_filter': account_id,
                'client_info': get_client_info()
            }
            
            return format_response(response_data, '/speech/byok/keys/list')
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/keys/list', 503)
        
    except Exception as e:
        logger.error(f"Failed to list provider keys: {e}")
        return format_error_response(str(e), '/speech/byok/keys/list', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/<key_id>", methods=["GET"])
@require_admin
async def get_provider_key(key_id):
    """Get specific provider key details"""
    try:
        if byok_manager:
            provider_key = byok_manager.get_provider_key(key_id)
            
            if provider_key:
                response_data = {
                    'key_id': provider_key.key_id,
                    'provider': provider_key.provider.value,
                    'key_name': provider_key.key_name,
                    'account_id': provider_key.account_id,
                    'account_name': provider_key.account_name,
                    'billing_id': provider_key.billing_id,
                    'key_permissions': provider_key.key_permissions,
                    'key_status': provider_key.key_status.value,
                    'rotation_status': provider_key.rotation_status.value,
                    'key_usage_count': provider_key.key_usage_count,
                    'key_last_used': provider_key.key_last_used.isoformat() if provider_key.key_last_used else None,
                    'key_expires_at': provider_key.key_expires_at.isoformat() if provider_key.key_expires_at else None,
                    'rotation_scheduled_at': provider_key.rotation_scheduled_at.isoformat() if provider_key.rotation_scheduled_at else None,
                    'rotation_frequency_days': provider_key.rotation_frequency_days,
                    'usage_quota': provider_key.usage_quota,
                    'usage_quota_period': provider_key.usage_quota_period,
                    'rate_limit_per_minute': provider_key.rate_limit_per_minute,
                    'cost_per_request': provider_key.cost_per_request,
                    'metadata': provider_key.metadata,
                    'created_at': provider_key.created_at.isoformat(),
                    'updated_at': provider_key.updated_at.isoformat()
                }
                
                return format_response(response_data, f'/speech/byok/keys/{key_id}')
            else:
                return format_error_response('Key not found', f'/speech/byok/keys/{key_id}', 404)
        else:
            return format_error_response('BYOK manager not available', f'/speech/byok/keys/{key_id}', 503)
        
    except Exception as e:
        logger.error(f"Failed to get provider key: {e}")
        return format_error_response(str(e), f'/speech/byok/keys/{key_id}', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/<key_id>/rotate", methods=["POST"])
@require_admin
async def rotate_provider_key(key_id):
    """Rotate a provider key"""
    try:
        request_data = request.get_json()
        
        rotation_type = request_data.get('rotation_type', 'manual')
        rotation_reason = request_data.get('rotation_reason', 'Manual rotation')
        new_key_data = request_data.get('new_key_data')
        
        if new_key_data:
            try:
                new_key_data = BYOKKeyRequest(**new_key_data)
            except Exception as e:
                return format_error_response(f'Invalid new_key_data: {e}', f'/speech/byok/keys/{key_id}/rotate', 400)
        
        if byok_manager:
            rotation = await byok_manager.rotate_key(
                key_id,
                rotation_type=rotation_type,
                new_key_data=new_key_data,
                rotation_reason=rotation_reason,
                created_by='admin'  # In production, get from authentication
            )
            
            if rotation:
                response_data = {
                    'rotation_id': rotation.rotation_id,
                    'key_id': rotation.key_id,
                    'old_key_id': rotation.old_key_id,
                    'new_key_id': rotation.new_key_id,
                    'rotation_type': rotation.rotation_type,
                    'rotation_status': rotation.rotation_status.value,
                    'rotation_started_at': rotation.rotation_started_at.isoformat() if rotation.rotation_started_at else None,
                    'rotation_completed_at': rotation.rotation_completed_at.isoformat() if rotation.rotation_completed_at else None,
                    'fallback_enabled': rotation.fallback_enabled,
                    'grace_period_days': rotation.grace_period_days,
                    'rollback_enabled': rotation.rollback_enabled,
                    'rotation_reason': rotation.rotation_reason,
                    'created_at': rotation.created_at.isoformat(),
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, f'/speech/byok/keys/{key_id}/rotate')
            else:
                return format_error_response('Failed to rotate key', f'/speech/byok/keys/{key_id}/rotate', 500)
        else:
            return format_error_response('BYOK manager not available', f'/speech/byok/keys/{key_id}/rotate', 503)
        
    except Exception as e:
        logger.error(f"Failed to rotate provider key: {e}")
        return format_error_response(str(e), f'/speech/byok/keys/{key_id}/rotate', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/<key_id>/revoke", methods=["POST"])
@require_admin
async def revoke_provider_key(key_id):
    """Revoke a provider key"""
    try:
        request_data = request.get_json()
        
        revoke_reason = request_data.get('revoke_reason', 'Manual revocation')
        
        if byok_manager:
            client_info = get_client_info()
            success = await byok_manager.revoke_key(
                key_id,
                revoke_reason=revoke_reason,
                revoked_by='admin',  # In production, get from authentication
                ip_address=client_info['ip_address'],
                user_agent=client_info['user_agent']
            )
            
            if success:
                response_data = {
                    'key_id': key_id,
                    'revoked': True,
                    'revoke_reason': revoke_reason,
                    'revoked_at': datetime.now(timezone.utc).isoformat(),
                    'client_info': client_info
                }
                
                return format_response(response_data, f'/speech/byok/keys/{key_id}/revoke')
            else:
                return format_error_response('Failed to revoke key', f'/speech/byok/keys/{key_id}/revoke', 500)
        else:
            return format_error_response('BYOK manager not available', f'/speech/byok/keys/{key_id}/revoke', 503)
        
    except Exception as e:
        logger.error(f"Failed to revoke provider key: {e}")
        return format_error_response(str(e), f'/speech/byok/keys/{key_id}/revoke', 500)

# === KEY USAGE ENDPOINTS ===

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/usage/report", methods=["POST"])
@require_admin
async def get_usage_report():
    """Get usage report for a key"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['key_id'])
        if not is_valid:
            return format_error_response(error, '/speech/byok/usage/report', 400)
        
        key_id = request_data['key_id']
        
        # Parse date range
        period_start = datetime.fromisoformat(request_data['period_start']) if request_data.get('period_start') else datetime.now(timezone.utc) - timedelta(days=30)
        period_end = datetime.fromisoformat(request_data['period_end']) if request_data.get('period_end') else datetime.now(timezone.utc)
        
        if byok_manager:
            report = await byok_manager.get_key_usage_report(key_id, period_start, period_end)
            
            if report:
                response_data = {
                    'report': report,
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/speech/byok/usage/report')
            else:
                return format_error_response('Failed to generate usage report', '/speech/byok/usage/report', 500)
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/usage/report', 503)
        
    except Exception as e:
        logger.error(f"Failed to get usage report: {e}")
        return format_error_response(str(e), '/speech/byok/usage/report', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/cost/report", methods=["POST"])
@require_admin
async def get_cost_report():
    """Get cost report"""
    try:
        request_data = request.get_json()
        
        # Parse parameters
        account_id = request_data.get('account_id')
        provider = request_data.get('provider')
        
        if provider:
            try:
                provider = ProviderType(provider)
            except ValueError:
                return format_error_response(f'Invalid provider: {provider}', '/speech/byok/cost/report', 400)
        
        period_start = datetime.fromisoformat(request_data['period_start']) if request_data.get('period_start') else datetime.now(timezone.utc).replace(day=1)
        period_end = datetime.fromisoformat(request_data['period_end']) if request_data.get('period_end') else datetime.now(timezone.utc)
        
        if byok_manager:
            report = await byok_manager.get_cost_report(account_id, provider, period_start, period_end)
            
            if report:
                response_data = {
                    'report': report,
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/speech/byok/cost/report')
            else:
                return format_error_response('Failed to generate cost report', '/speech/byok/cost/report', 500)
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/cost/report', 503)
        
    except Exception as e:
        logger.error(f"Failed to get cost report: {e}")
        return format_error_response(str(e), '/speech/byok/cost/report', 500)

# === KEY ACCESS ENDPOINTS ===

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/active", methods=["GET"])
async def get_active_key():
    """Get active key for a provider (for transcription service)"""
    try:
        provider = request.args.get('provider')
        account_id = request.args.get('account_id')
        
        if not provider:
            return format_error_response('Provider parameter is required', '/speech/byok/keys/active', 400)
        
        try:
            provider_type = ProviderType(provider)
        except ValueError:
            return format_error_response(f'Invalid provider: {provider}', '/speech/byok/keys/active', 400)
        
        if byok_manager:
            active_key = await byok_manager.get_active_key(provider_type, account_id)
            
            if active_key:
                client_info = get_client_info()
                
                # Log key access
                await byok_manager.update_key_usage(
                    active_key.key_id,
                    'key_access',
                    0,  # No audio duration for access
                    0,  # No cost for access
                    request.headers.get('X-Request-ID', f"req_{secrets.token_urlsafe(16)}"),
                    user_id=client_info.get('user_id', 'system'),
                    ip_address=client_info['ip_address'],
                    user_agent=client_info['user_agent']
                )
                
                # Get decrypted key (only for internal use)
                decrypted_key = await byok_manager.get_decrypted_key(
                    active_key.key_id,
                    client_info.get('user_id', 'system'),
                    client_info['ip_address'],
                    client_info['user_agent']
                )
                
                response_data = {
                    'key_id': active_key.key_id,
                    'provider': active_key.provider.value,
                    'account_name': active_key.account_name,
                    'api_key': decrypted_key,  # Only returned for internal service use
                    'rate_limit_per_minute': active_key.rate_limit_per_minute,
                    'key_status': active_key.key_status.value,
                    'last_used': active_key.key_last_used.isoformat() if active_key.key_last_used else None,
                    'client_info': client_info
                }
                
                return format_response(response_data, '/speech/byok/keys/active')
            else:
                return format_error_response('No active key found for provider', '/speech/byok/keys/active', 404)
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/keys/active', 503)
        
    except Exception as e:
        logger.error(f"Failed to get active key: {e}")
        return format_error_response(str(e), '/speech/byok/keys/active', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/keys/<key_id>/access", methods=["POST"])
async def access_key():
    """Access decrypted key for transcription (internal service)"""
    try:
        request_data = request.get_json()
        
        # Validate service token
        service_token = request.headers.get('X-Service-Token')
        if not service_token or service_token != os.getenv('BYOK_SERVICE_TOKEN', 'service-secret'):
            return format_error_response('Service authentication required', '/speech/byok/keys/access', 403)
        
        key_id = request.view_args.get('key_id')
        usage_type = request_data.get('usage_type', 'transcription')
        meeting_id = request_data.get('meeting_id')
        participant_id = request_data.get('participant_id')
        
        if byok_manager:
            client_info = get_client_info()
            decrypted_key = await byok_manager.get_decrypted_key(
                key_id,
                client_info.get('user_id', 'service'),
                client_info['ip_address'],
                client_info['user_agent']
            )
            
            if decrypted_key:
                # Log access
                await byok_manager.update_key_usage(
                    key_id,
                    usage_type,
                    request_data.get('audio_duration', 0),
                    request_data.get('cost_incurred', 0),
                    request.headers.get('X-Request-ID', f"req_{secrets.token_urlsafe(16)}"),
                    meeting_id=meeting_id,
                    participant_id=participant_id,
                    user_id=client_info.get('user_id', 'service'),
                    ip_address=client_info['ip_address'],
                    user_agent=client_info['user_agent'],
                    metadata=request_data.get('metadata')
                )
                
                response_data = {
                    'key_id': key_id,
                    'api_key': decrypted_key,
                    'provider': byok_manager.get_provider_key(key_id).provider.value,
                    'usage_type': usage_type,
                    'accessed_at': datetime.now(timezone.utc).isoformat(),
                    'client_info': client_info
                }
                
                return format_response(response_data, f'/speech/byok/keys/{key_id}/access')
            else:
                return format_error_response('Failed to access key', f'/speech/byok/keys/{key_id}/access', 500)
        else:
            return format_error_response('BYOK manager not available', f'/speech/byok/keys/{key_id}/access', 503)
        
    except Exception as e:
        logger.error(f"Failed to access key: {e}")
        return format_error_response(str(e), f'/speech/byok/keys/{key_id}/access', 500)

# === MONITORING ENDPOINTS ===

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/metrics", methods=["GET"])
@require_admin
async def get_byok_metrics():
    """Get BYOK system metrics"""
    try:
        if byok_manager:
            metrics = byok_manager.get_metrics()
            
            # Get additional system information
            keys = byok_manager.get_all_keys()
            active_keys = byok_manager.get_active_keys()
            
            # Metrics by provider
            keys_by_provider = {}
            for key in keys:
                provider = key.provider.value
                if provider not in keys_by_provider:
                    keys_by_provider[provider] = {'total': 0, 'active': 0, 'inactive': 0}
                keys_by_provider[provider]['total'] += 1
                if key.key_status == KeyStatus.ACTIVE:
                    keys_by_provider[provider]['active'] += 1
                else:
                    keys_by_provider[provider]['inactive'] += 1
            
            response_data = {
                'system_metrics': metrics,
                'key_statistics': {
                    'total_keys': len(keys),
                    'active_keys': len(active_keys),
                    'keys_by_provider': keys_by_provider,
                    'keys_expiring_soon': len([
                        key for key in active_keys
                        if key.key_expires_at and key.key_expires_at <= datetime.now(timezone.utc) + timedelta(days=7)
                    ]),
                    'keys_needing_rotation': len([
                        key for key in active_keys
                        if key.rotation_status.value == 'scheduled' or
                           (key.key_expires_at and key.key_expires_at <= datetime.now(timezone.utc) + timedelta(days=key.rotation_frequency_days))
                    ])
                },
                'system_health': {
                    'manager_running': byok_manager.is_running,
                    'background_tasks': len(byok_manager.background_tasks),
                    'http_clients': len(byok_manager.http_clients),
                    'encryption_enabled': True,
                    'auto_rotation_enabled': byok_manager.key_rotation_config['auto_rotation_enabled']
                },
                'client_info': get_client_info()
            }
            
            return format_response(response_data, '/speech/byok/metrics')
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/metrics', 503)
        
    except Exception as e:
        logger.error(f"Failed to get BYOK metrics: {e}")
        return format_error_response(str(e), '/speech/byok/metrics', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/health", methods=["GET"])
async def byok_health_check():
    """Health check for BYOK system"""
    try:
        health_status = {
            'byok_manager': byok_manager is not None,
            'manager_running': byok_manager.is_running if byok_manager else False,
            'encryption_available': True,
            'database_connected': bool(byok_manager.db_pool) if byok_manager else False
        }
        
        # Get detailed status if available
        if byok_manager:
            health_status['background_tasks'] = len(byok_manager.background_tasks)
            health_status['total_keys_managed'] = len(byok_manager.provider_keys)
            health_status['active_keys'] = len(byok_manager.get_active_keys())
            health_status['rotation_config'] = byok_manager.key_rotation_config
            health_status['performance_metrics'] = {
                'keys_managed': byok_manager.metrics['keys_managed'],
                'encryption_operations': byok_manager.metrics['encryption_operations'],
                'decryption_operations': byok_manager.metrics['decryption_operations'],
                'key_rotations': byok_manager.metrics['key_rotations'],
                'usage_logs': byok_manager.metrics['usage_logs'],
                'quota_violations': byok_manager.metrics['quota_violations'],
                'security_incidents': byok_manager.metrics['security_incidents']
            }
        
        # Determine overall health
        is_healthy = (
            health_status['byok_manager'] and 
            health_status['manager_running'] and 
            health_status['encryption_available'] and
            health_status['database_connected']
        )
        
        if is_healthy:
            return format_response(health_status, '/speech/byok/health')
        else:
            return format_error_response('BYOK system unhealthy', '/speech/byok/health', 503)
        
    except Exception as e:
        logger.error(f"BYOK health check failed: {e}")
        return format_error_response(f'Health check failed: {e}', '/speech/byok/health', 500)

# === CONFIGURATION ENDPOINTS ===

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/config/rotation", methods=["GET"])
@require_admin
async def get_rotation_config():
    """Get key rotation configuration"""
    try:
        if byok_manager:
            response_data = {
                'rotation_config': byok_manager.key_rotation_config,
                'client_info': get_client_info()
            }
            
            return format_response(response_data, '/speech/byok/config/rotation')
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/config/rotation', 503)
        
    except Exception as e:
        logger.error(f"Failed to get rotation config: {e}")
        return format_error_response(str(e), '/speech/byok/config/rotation', 500)

@zoom_speech_byok_bp.route("/api/zoom/speech/byok/config/rotation", methods=["POST"])
@require_admin
async def update_rotation_config():
    """Update key rotation configuration"""
    try:
        request_data = request.get_json()
        
        if byok_manager:
            # Update rotation config
            for key, value in request_data.items():
                if key in byok_manager.key_rotation_config:
                    byok_manager.key_rotation_config[key] = value
            
            response_data = {
                'rotation_config': byok_manager.key_rotation_config,
                'updated_at': datetime.now(timezone.utc).isoformat(),
                'client_info': get_client_info()
            }
            
            return format_response(response_data, '/speech/byok/config/rotation')
        else:
            return format_error_response('BYOK manager not available', '/speech/byok/config/rotation', 503)
        
    except Exception as e:
        logger.error(f"Failed to update rotation config: {e}")
        return format_error_response(str(e), '/speech/byok/config/rotation', 500)

# === ERROR HANDLING ===

@zoom_speech_byok_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return format_error_response('Bad Request', 'global', 400)

@zoom_speech_byok_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized"""
    return format_error_response('Unauthorized', 'global', 401)

@zoom_speech_byok_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden"""
    return format_error_response('Forbidden', 'global', 403)

@zoom_speech_byok_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return format_error_response('Not Found', 'global', 404)

@zoom_speech_byok_bp.errorhandler(429)
def rate_limited(error):
    """Handle 429 Too Many Requests"""
    return format_error_response('Rate Limit Exceeded', 'global', 429)

@zoom_speech_byok_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error"""
    logger.error(f"Internal server error: {error}")
    return format_error_response('Internal Server Error', 'global', 500)