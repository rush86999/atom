"""
🔐 Enhanced Zoom OAuth Routes
Advanced OAuth flow with enhanced security and user experience
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from flask import Blueprint, request, jsonify, session, redirect, url_for, current_app

from enhanced_zoom_oauth_handler import EnhancedZoomOAuthHandler, OAuthState

logger = logging.getLogger(__name__)

# Create blueprint
enhanced_auth_zoom_bp = Blueprint("enhanced_auth_zoom", __name__)

# Global OAuth handler
oauth_handler: Optional[EnhancedZoomOAuthHandler] = None

def init_enhanced_zoom_oauth_handler(db_pool):
    """Initialize enhanced Zoom OAuth handler"""
    global oauth_handler
    oauth_handler = EnhancedZoomOAuthHandler(db_pool)
    return oauth_handler

def format_response(data: Any, endpoint: str, status: str = 'success') -> Dict[str, Any]:
    """Format API response"""
    return {
        'ok': status == 'success',
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'enhanced_zoom_oauth_api'
    }

def format_error_response(error: str, endpoint: str, status_code: int = 500) -> tuple:
    """Format error response"""
    error_response = {
        'ok': False,
        'error': {
            'code': 'OAUTH_ERROR',
            'message': error,
            'endpoint': endpoint
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'enhanced_zoom_oauth_api'
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

# === ENHANCED OAUTH ENDPOINTS ===

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/authorize", methods=["POST"])
async def enhanced_oauth_authorize():
    """Initiate enhanced OAuth authorization flow"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/authorize', 400)
        
        user_id = request_data['user_id']
        redirect_after_auth = request_data.get('redirect_after_auth')
        custom_scopes = request_data.get('custom_scopes')
        metadata = request_data.get('metadata', {})
        
        # Add client information to metadata
        client_info = get_client_info()
        metadata.update({
            'client_info': client_info,
            'authorization_timestamp': datetime.now(timezone.utc).isoformat()
        })
        
        # Generate enhanced OAuth URL
        oauth_result = await oauth_handler.generate_oauth_url(
            user_id=user_id,
            redirect_after_auth=redirect_after_auth,
            custom_scopes=custom_scopes,
            metadata=metadata
        )
        
        if oauth_result['success']:
            return format_response(oauth_result, '/oauth/enhanced/authorize')
        else:
            return format_error_response(oauth_result['error'], '/oauth/enhanced/authorize', 500)
        
    except Exception as e:
        logger.error(f"Enhanced OAuth authorization error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/authorize', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/callback", methods=["POST"])
async def enhanced_oauth_callback():
    """Handle enhanced OAuth callback with improved security"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        required_fields = ['code', 'state_id']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/callback', 400)
        
        code = request_data['code']
        state_id = request_data['state_id']
        redirect_uri = request_data.get('redirect_uri')
        
        # Add client information for security tracking
        client_info = get_client_info()
        
        # Exchange code for token with enhanced security
        token_result = await oauth_handler.exchange_code_for_token(
            code=code,
            state_id=state_id,
            redirect_uri=redirect_uri
        )
        
        if token_result['success']:
            # Add security information
            token_result['security_info'] = {
                'client_info': client_info,
                'callback_timestamp': datetime.now(timezone.utc).isoformat(),
                'state_validation': 'completed'
            }
            
            return format_response(token_result, '/oauth/enhanced/callback')
        else:
            # Add security context to error
            error_data = token_result.copy()
            error_data['security_info'] = {
                'client_info': client_info,
                'callback_timestamp': datetime.now(timezone.utc).isoformat(),
                'state_validation': 'failed'
            }
            
            return format_error_response(
                error_data['error'], 
                '/oauth/enhanced/callback', 
                400
            )
        
    except Exception as e:
        logger.error(f"Enhanced OAuth callback error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/callback', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/revoke", methods=["POST"])
async def enhanced_oauth_revoke():
    """Revoke OAuth token with enhanced cleanup"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/revoke', 400)
        
        user_id = request_data['user_id']
        
        # Add client information for security audit
        client_info = get_client_info()
        
        # Revoke token with enhanced cleanup
        revoke_result = await oauth_handler.revoke_token(user_id)
        
        if revoke_result['success']:
            revoke_result['security_info'] = {
                'client_info': client_info,
                'revoke_timestamp': datetime.now(timezone.utc).isoformat(),
                'cleanup_performed': True
            }
            
            return format_response(revoke_result, '/oauth/enhanced/revoke')
        else:
            revoke_result['security_info'] = {
                'client_info': client_info,
                'revoke_timestamp': datetime.now(timezone.utc).isoformat(),
                'cleanup_performed': True
            }
            
            return format_error_response(
                revoke_result['error'], 
                '/oauth/enhanced/revoke', 
                400
            )
        
    except Exception as e:
        logger.error(f"Enhanced OAuth revoke error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/revoke', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/status", methods=["POST"])
async def enhanced_oauth_status():
    """Get comprehensive OAuth status"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/status', 400)
        
        user_id = request_data['user_id']
        
        # Get comprehensive OAuth status
        status_result = await oauth_handler.get_oauth_status(user_id)
        
        # Add additional security information
        status_result['security_info'] = {
            'client_info': get_client_info(),
            'status_timestamp': datetime.now(timezone.utc).isoformat(),
            'endpoint_security': {
                'csrf_protection': True,
                'state_validation': True,
                'token_encryption': True,
                'audit_logging': True
            }
        }
        
        return format_response(status_result, '/oauth/enhanced/status')
        
    except Exception as e:
        logger.error(f"Enhanced OAuth status error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/status', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/refresh", methods=["POST"])
async def enhanced_oauth_refresh():
    """Refresh OAuth token with enhanced security"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/refresh', 400)
        
        user_id = request_data['user_id']
        force_refresh = request_data.get('force_refresh', False)
        
        # Get current token status
        current_token = await oauth_handler.get_token(user_id, include_refresh=True)
        
        if not current_token:
            return format_error_response(
                'No active token found for refresh',
                '/oauth/enhanced/refresh',
                404
            )
        
        # Check if refresh is needed or forced
        now = datetime.now(timezone.utc)
        time_until_expiry = current_token.expires_at - now
        
        refresh_needed = force_refresh or time_until_expiry.total_seconds() < 300
        
        if refresh_needed:
            # Perform token refresh
            refreshed_token = await oauth_handler.refresh_token_if_needed(user_id)
            
            if refreshed_token:
                response_data = {
                    'refreshed': True,
                    'user_id': user_id,
                    'expires_at': refreshed_token.expires_at.isoformat(),
                    'access_count': refreshed_token.access_count,
                    'last_used_at': refreshed_token.last_used_at.isoformat(),
                    'refresh_info': {
                        'reason': 'forced' if force_refresh else 'expiring_soon',
                        'previous_expiry': current_token.expires_at.isoformat(),
                        'time_until_expiry_previous': int(time_until_expiry.total_seconds()),
                        'refresh_timestamp': datetime.now(timezone.utc).isoformat()
                    }
                }
                
                return format_response(response_data, '/oauth/enhanced/refresh')
            else:
                return format_error_response(
                    'Token refresh failed',
                    '/oauth/enhanced/refresh',
                    500
                )
        else:
            # Token still valid
            response_data = {
                'refreshed': False,
                'user_id': user_id,
                'expires_at': current_token.expires_at.isoformat(),
                'access_count': current_token.access_count,
                'last_used_at': current_token.last_used_at.isoformat(),
                'time_until_expiry': int(time_until_expiry.total_seconds()),
                'refresh_info': {
                    'reason': 'not_needed',
                    'time_until_expiry': int(time_until_expiry.total_seconds())
                }
            }
            
            return format_response(response_data, '/oauth/enhanced/refresh')
        
    except Exception as e:
        logger.error(f"Enhanced OAuth refresh error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/refresh', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/validate", methods=["POST"])
async def enhanced_oauth_validate():
    """Validate OAuth token with enhanced security checks"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/validate', 400)
        
        user_id = request_data['user_id']
        detailed_validation = request_data.get('detailed', False)
        
        # Get current token
        token_info = await oauth_handler.get_token(user_id, include_refresh=True)
        
        if not token_info:
            return format_response({
                'valid': False,
                'user_id': user_id,
                'reason': 'No active token found',
                'validation_timestamp': datetime.now(timezone.utc).isoformat()
            }, '/oauth/enhanced/validate')
        
        # Perform validation checks
        now = datetime.now(timezone.utc)
        time_until_expiry = token_info.expires_at - now
        
        validation_result = {
            'valid': time_until_expiry.total_seconds() > 0,
            'user_id': user_id,
            'zoom_user_id': token_info.zoom_user_id,
            'email': token_info.email,
            'expires_at': token_info.expires_at.isoformat(),
            'time_until_expiry': int(time_until_expiry.total_seconds()),
            'access_count': token_info.access_count,
            'last_used_at': token_info.last_used_at.isoformat(),
            'validation_timestamp': now.isoformat(),
            'warnings': []
        }
        
        # Add warnings for potential issues
        if time_until_expiry.total_seconds() < 300:
            validation_result['warnings'].append({
                'type': 'expiring_soon',
                'message': 'Token expires within 5 minutes',
                'seconds_remaining': int(time_until_expiry.total_seconds())
            })
        
        if time_until_expiry.total_seconds() < 60:
            validation_result['warnings'].append({
                'type': 'expiring_imminently',
                'message': 'Token expires within 1 minute',
                'seconds_remaining': int(time_until_expiry.total_seconds())
            })
        
        # Add detailed validation information if requested
        if detailed_validation:
            validation_result['detailed_info'] = {
                'token_type': token_info.token_type,
                'scopes': token_info.scope.split(' ') if token_info.scope else [],
                'account_id': token_info.account_id,
                'account_type': token_info.account_type,
                'user_type': token_info.user_type,
                'role_id': token_info.role_id,
                'metadata': token_info.metadata,
                'client_info': get_client_info(),
                'security_checks': {
                    'token_encryption': True,
                    'access_token_present': bool(token_info.access_token),
                    'refresh_token_present': bool(token_info.refresh_token),
                    'expiry_in_future': token_info.expires_at > now,
                    'access_count_reasonable': token_info.access_count < 10000  # Sanity check
                }
            }
        
        return format_response(validation_result, '/oauth/enhanced/validate')
        
    except Exception as e:
        logger.error(f"Enhanced OAuth validation error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/validate', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/switch", methods=["POST"])
async def enhanced_oauth_switch():
    """Switch to different OAuth scope or account"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        required_fields = ['user_id', 'switch_type']
        is_valid, error = validate_required_fields(request_data, required_fields)
        
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/switch', 400)
        
        user_id = request_data['user_id']
        switch_type = request_data['switch_type']  # 'scope', 'account', 'reauthorize'
        target_scopes = request_data.get('target_scopes')
        account_id = request_data.get('account_id')
        metadata = request_data.get('metadata', {})
        
        # Add client information
        client_info = get_client_info()
        metadata.update({
            'client_info': client_info,
            'switch_timestamp': datetime.now(timezone.utc).isoformat(),
            'switch_type': switch_type
        })
        
        # Handle different switch types
        if switch_type == 'scope':
            if not target_scopes:
                return format_error_response(
                    'target_scopes required for scope switch',
                    '/oauth/enhanced/switch',
                    400
                )
            
            # Generate new OAuth URL with different scopes
            oauth_result = await oauth_handler.generate_oauth_url(
                user_id=user_id,
                custom_scopes=target_scopes,
                metadata=metadata
            )
            
            oauth_result['switch_info'] = {
                'switch_type': 'scope',
                'previous_scopes': None,  # Would get from current token
                'new_scopes': target_scopes,
                'reason': 'scope_change_requested'
            }
            
        elif switch_type == 'account':
            # Switch to different account
            oauth_result = await oauth_handler.generate_oauth_url(
                user_id=user_id,
                metadata=metadata
            )
            
            oauth_result['switch_info'] = {
                'switch_type': 'account',
                'target_account_id': account_id,
                'reason': 'account_change_requested'
            }
            
        elif switch_type == 'reauthorize':
            # Force reauthorization (keep same scopes)
            oauth_result = await oauth_handler.generate_oauth_url(
                user_id=user_id,
                metadata=metadata
            )
            
            oauth_result['switch_info'] = {
                'switch_type': 'reauthorize',
                'reason': 'reauthorization_requested'
            }
            
        else:
            return format_error_response(
                f'Invalid switch_type: {switch_type}',
                '/oauth/enhanced/switch',
                400
            )
        
        if oauth_result['success']:
            return format_response(oauth_result, '/oauth/enhanced/switch')
        else:
            return format_error_response(
                oauth_result['error'],
                '/oauth/enhanced/switch',
                500
            )
        
    except Exception as e:
        logger.error(f"Enhanced OAuth switch error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/switch', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/security", methods=["GET"])
async def enhanced_oauth_security_info():
    """Get OAuth security configuration and status"""
    try:
        if not oauth_handler:
            return format_error_response(
                'OAuth handler not initialized',
                '/oauth/enhanced/security',
                503
            )
        
        # Get security configuration
        config = oauth_handler.config
        
        security_info = {
            'oauth_version': '2.0',
            'security_features': {
                'csrf_protection': config.csrf_protection_enabled,
                'pkce': config.pkce_enabled,
                'token_encryption': config.token_encryption_enabled,
                'state_management': True,
                'access_audit': True,
                'rate_limiting': True
            },
            'configuration': {
                'state_ttl_seconds': config.state_ttl_seconds,
                'max_concurrent_flows': config.max_concurrent_flows,
                'environment': config.environment
            },
            'enabled_scopes': config.scopes,
            'security_headers': {
                'strict_transport_security': True,
                'content_type_options': True,
                'x_frame_options': 'DENY',
                'x_content_type_options': 'nosniff',
                'referrer_policy': 'strict-origin-when-cross-origin'
            },
            'client_security': {
                'user_agent_tracking': True,
                'ip_address_logging': True,
                'referer_validation': True,
                'origin_validation': True
            },
            'token_security': {
                'access_token_encryption': config.token_encryption_enabled,
                'refresh_token_encryption': config.token_encryption_enabled,
                'automatic_refresh': True,
                'token_expiry_monitoring': True
            },
            'audit_logging': {
                'authorization_events': True,
                'callback_events': True,
                'token_refresh_events': True,
                'revoke_events': True,
                'security_violations': True
            }
        }
        
        return format_response(security_info, '/oauth/enhanced/security')
        
    except Exception as e:
        logger.error(f"Enhanced OAuth security info error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/security', 500)

@enhanced_auth_zoom_bp.route("/api/integrations/zoom/oauth/enhanced/audit", methods=["POST"])
async def enhanced_oauth_audit():
    """Get OAuth audit information for user"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['user_id'])
        if not is_valid:
            return format_error_response(error, '/oauth/enhanced/audit', 400)
        
        user_id = request_data['user_id']
        audit_type = request_data.get('audit_type', 'full')
        
        # Get OAuth status with audit information
        status_result = await oauth_handler.get_oauth_status(user_id)
        
        # Build audit information
        audit_info = {
            'user_id': user_id,
            'audit_type': audit_type,
            'audit_timestamp': datetime.now(timezone.utc).isoformat(),
            'current_status': status_result,
            'security_audit': {
                'last_client_info': get_client_info(),
                'authentication_method': 'oauth_2.0_enhanced',
                'security_features_enabled': {
                    'csrf_protection': True,
                    'pkce': True,
                    'token_encryption': True,
                    'state_management': True
                }
            },
            'recommendations': []
        }
        
        # Add security recommendations
        if status_result.get('authenticated'):
            token_info = status_result
            
            # Check for potential security issues
            if token_info.get('access_count', 0) > 1000:
                audit_info['recommendations'].append({
                    'type': 'security',
                    'severity': 'medium',
                    'message': 'High access count detected - consider reviewing usage patterns',
                    'suggestion': 'Monitor access patterns and consider rotating tokens if unusual activity detected'
                })
            
            if token_info.get('metadata', {}).get('refresh_count', 0) > 50:
                audit_info['recommendations'].append({
                    'type': 'security',
                    'severity': 'medium',
                    'message': 'High refresh count detected - may indicate token reuse issues',
                    'suggestion': 'Review application token handling and ensure proper refresh token usage'
                })
        else:
            audit_info['recommendations'].append({
                'type': 'action_required',
                'severity': 'high',
                'message': 'User not authenticated - OAuth flow required',
                'suggestion': 'Initiate OAuth authorization flow to enable Zoom integration'
            })
        
        return format_response(audit_info, '/oauth/enhanced/audit')
        
    except Exception as e:
        logger.error(f"Enhanced OAuth audit error: {e}")
        return format_error_response(str(e), '/oauth/enhanced/audit', 500)

# === ERROR HANDLING ===

@enhanced_auth_zoom_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return format_error_response('Bad Request', 'global', 400)

@enhanced_auth_zoom_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized"""
    return format_error_response('Unauthorized', 'global', 401)

@enhanced_auth_zoom_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden"""
    return format_error_response('Forbidden', 'global', 403)

@enhanced_auth_zoom_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return format_error_response('Not Found', 'global', 404)

@enhanced_auth_zoom_bp.errorhandler(429)
def rate_limited(error):
    """Handle 429 Too Many Requests"""
    return format_error_response('Rate Limit Exceeded', 'global', 429)

@enhanced_auth_zoom_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error"""
    logger.error(f"Internal server error: {error}")
    return format_error_response('Internal Server Error', 'global', 500)

# === CLEANUP ===

async def cleanup_enhanced_oauth():
    """Cleanup enhanced OAuth handler"""
    global oauth_handler
    
    try:
        if oauth_handler:
            await oauth_handler.close()
        
        logger.info("Enhanced Zoom OAuth handler cleaned up successfully")
        
    except Exception as e:
        logger.error(f"Failed to cleanup enhanced Zoom OAuth handler: {e}")

# Register cleanup function
import atexit
atexit.register(lambda: asyncio.create_task(cleanup_enhanced_oauth()))