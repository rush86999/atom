"""
ATOM Enterprise API Routes
Advanced enterprise-grade API endpoints with comprehensive automation integration
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from flask import Blueprint, request, jsonify, current_app
from flask_jwt_extended import jwt_required, create_access_token, get_jwt_identity, get_jwt
from loguru import logger
from functools import wraps

# Import enterprise services
try:
    from atom_enterprise_security_service import atom_enterprise_security_service, SecurityPolicy, ThreatDetection, ComplianceReport, SecurityAudit, SecurityLevel, ComplianceStandard, ThreatType, AuditEventType
    from atom_enterprise_unified_service import atom_enterprise_unified_service, EnterpriseWorkflow, SecurityWorkflowAction, ComplianceAutomation, EnterpriseServiceType, WorkflowSecurityLevel, ComplianceWorkflowType, AutomationTriggerType
    from atom_workflow_automation_service import atom_workflow_automation_service, WorkflowAutomation, AutomationExecution, WorkflowAutomationType, AutomationActionType, AutomationConditionType, AutomationPriority, AutomationStatus
    from atom_workflow_service import AtomWorkflowService
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_ingestion_pipeline import AtomIngestionPipeline
    from ai_enhanced_service import ai_enhanced_service, AIRequest, AIResponse, AITaskType, AIModelType, AIServiceType
    from atom_ai_integration import atom_ai_integration
    from atom_slack_integration import atom_slack_integration
    from atom_teams_integration import atom_teams_integration
    from atom_google_chat_integration import atom_google_chat_integration
    from atom_discord_integration import atom_discord_integration
except ImportError as e:
    logger.warning(f"Enterprise services not available: {e}")
    atom_enterprise_security_service = None
    atom_enterprise_unified_service = None
    atom_workflow_automation_service = None
    AtomWorkflowService = None
    AtomMemoryService = None
    AtomSearchService = None
    AtomIngestionPipeline = None
    ai_enhanced_service = None
    atom_ai_integration = None

# Create enterprise API blueprint
enterprise_bp = Blueprint('enterprise_api', __name__, url_prefix='/api/enterprise')

# Enterprise configuration validation
def validate_enterprise_config():
    """Validate enterprise configuration"""
    required_vars = [
        'ENTERPRISE_ENCRYPTION_KEY',
        'ENTERPRISE_JWT_SECRET',
        'ENTERPRISE_SESSION_SECRET',
        'ENTERPRISE_DATABASE_URI'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required enterprise environment variables: {missing_vars}")
        return False
    
    return True

# Enterprise decorators
def require_enterprise_role(required_role: str):
    """Decorator to require specific enterprise role"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_roles = claims.get('roles', [])
            
            if required_role not in user_roles:
                return {
                    'error': 'Insufficient permissions',
                    'required_role': required_role,
                    'user_roles': user_roles
                }, 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

def require_security_level(required_level: SecurityLevel):
    """Decorator to require specific security level"""
    def decorator(f):
        @wraps(f)
        @jwt_required()
        def decorated_function(*args, **kwargs):
            claims = get_jwt()
            user_security_level = claims.get('security_level', 'basic')
            
            # Convert to SecurityLevel enum
            user_level = SecurityLevel(user_security_level)
            required = SecurityLevel(required_level)
            
            # Check hierarchy
            level_hierarchy = {
                SecurityLevel.BASIC: 0,
                SecurityLevel.STANDARD: 1,
                SecurityLevel.ADVANCED: 2,
                SecurityLevel.ENTERPRISE: 3,
                SecurityLevel.GOVERNMENT: 4
            }
            
            if level_hierarchy[user_level] < level_hierarchy[required]:
                return {
                    'error': 'Insufficient security level',
                    'required_level': required_level.value,
                    'user_level': user_level.value
                }, 403
            
            return f(*args, **kwargs)
        return decorated_function
    return decorator

# Utility functions
def create_enterprise_response(ok: bool, data: Any = None, error: str = None,
                            message: str = None, metadata: Dict = None) -> Dict[str, Any]:
    """Create standardized enterprise API response"""
    response = {
        'ok': ok,
        'timestamp': datetime.utcnow().isoformat(),
        'api_version': '6.0.0',
        'service': 'Enterprise Services'
    }
    
    if ok:
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
        if metadata:
            response['metadata'] = metadata
    else:
        response['error'] = error or 'Unknown error occurred'
    
    return response

def get_enterprise_request_data() -> Dict[str, Any]:
    """Get and validate enterprise request data"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id') or get_jwt_identity() if get_jwt_identity() else 'enterprise-user'
        data['user_id'] = user_id
        return data
    except Exception as e:
        logger.error(f"Error parsing enterprise request data: {e}")
        return {}

# Enterprise Authentication
@enterprise_bp.route('/auth/login', methods=['POST'])
def enterprise_login():
    """Enterprise authentication with security checks"""
    try:
        data = get_enterprise_request_data()
        username = data.get('username')
        password = data.get('password')
        remember = data.get('remember', False)
        security_level = data.get('security_level', 'standard')
        
        if not all([username, password]):
            return create_enterprise_response(False, error="username and password are required"), 400
        
        if not validate_enterprise_config():
            return create_enterprise_response(False, error="Enterprise configuration validation failed"), 500
        
        # Validate password strength
        if atom_enterprise_security_service:
            password_validation = await atom_enterprise_security_service.validate_password(password)
            if not password_validation['valid']:
                return create_enterprise_response(False, error=f"Password validation failed: {password_validation['issues']}"), 400
        
        # Verify credentials (mock implementation)
        user_data = await _verify_enterprise_credentials(username, password)
        if not user_data:
            # Log failed login attempt
            if atom_enterprise_security_service:
                await atom_enterprise_security_service.audit_event({
                    'event_type': AuditEventType.ACCESS_DENIED.value,
                    'user_id': username,
                    'resource': 'enterprise_auth',
                    'action': 'login',
                    'result': 'failed',
                    'ip_address': request.remote_addr,
                    'user_agent': request.headers.get('User-Agent', ''),
                    'metadata': {'reason': 'invalid_credentials'}
                })
            
            return create_enterprise_response(False, error="Invalid credentials"), 401
        
        # Create enterprise session
        session_data = {
            'user_id': user_data['user_id'],
            'username': user_data['username'],
            'roles': user_data['roles'],
            'security_level': user_data['security_level'],
            'permissions': user_data['permissions'],
            'login_time': datetime.utcnow().isoformat(),
            'ip_address': request.remote_addr,
            'user_agent': request.headers.get('User-Agent', '')
        }
        
        # Create JWT token with enterprise claims
        additional_claims = {
            'roles': user_data['roles'],
            'security_level': user_data['security_level'],
            'permissions': user_data['permissions'],
            'enterprise': True
        }
        
        if remember:
            expires_delta = timedelta(days=7)
        else:
            expires_delta = timedelta(hours=1)
        
        access_token = create_access_token(
            identity=user_data['user_id'],
            additional_claims=additional_claims,
            expires_delta=expires_delta
        )
        
        # Log successful login
        if atom_enterprise_security_service:
            await atom_enterprise_security_service.audit_event({
                'event_type': AuditEventType.USER_LOGIN.value,
                'user_id': user_data['user_id'],
                'resource': 'enterprise_auth',
                'action': 'login',
                'result': 'success',
                'ip_address': request.remote_addr,
                'user_agent': request.headers.get('User-Agent', ''),
                'metadata': {'remember': remember, 'security_level': security_level}
            })
        
        return create_enterprise_response(
            True,
            data={
                'access_token': access_token,
                'user': {
                    'id': user_data['user_id'],
                    'username': user_data['username'],
                    'roles': user_data['roles'],
                    'security_level': user_data['security_level'],
                    'permissions': user_data['permissions']
                },
                'session': session_data,
                'expires_in': expires_delta.total_seconds()
            },
            message="Enterprise authentication successful"
        )
    
    except Exception as e:
        logger.error(f"Enterprise login error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

# Workflow Automation Management
@enterprise_bp.route('/automation/create', methods=['POST'])
@jwt_required()
@require_enterprise_role('automation_admin')
@require_security_level(SecurityLevel.ENTERPRISE)
def create_workflow_automation():
    """Create workflow automation"""
    try:
        data = get_enterprise_request_data()
        automation_name = data.get('name')
        description = data.get('description')
        automation_type = data.get('automation_type')
        priority = data.get('priority')
        conditions = data.get('conditions', [])
        actions = data.get('actions', [])
        schedule = data.get('schedule')
        timeout = data.get('timeout', 3600)
        retry_policy = data.get('retry_policy', {
            'max_retries': 3,
            'backoff': 'exponential'
        })
        notification_rules = data.get('notification_rules', [])
        user_id = data.get('user_id')
        
        if not all([automation_name, description, automation_type, priority]):
            return create_enterprise_response(False, error="name, description, automation_type, and priority are required"), 400
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Create automation
        automation_data = {
            'name': automation_name,
            'description': description,
            'automation_type': automation_type,
            'priority': priority,
            'conditions': conditions,
            'actions': actions,
            'schedule': schedule,
            'timeout': timeout,
            'retry_policy': retry_policy,
            'notification_rules': notification_rules,
            'metadata': data.get('metadata', {})
        }
        
        result = await atom_workflow_automation_service.create_automation(automation_data, user_id)
        
        if result.get('ok'):
            return create_enterprise_response(
                True,
                data=result,
                message="Workflow automation created successfully"
            )
        else:
            return create_enterprise_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Create workflow automation error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/execute', methods=['POST'])
@jwt_required()
@require_security_level(SecurityLevel.STANDARD)
def execute_workflow_automation():
    """Execute workflow automation"""
    try:
        data = get_enterprise_request_data()
        automation_id = data.get('automation_id')
        trigger_context = data.get('trigger_context', {})
        triggered_by = data.get('triggered_by')
        user_id = data.get('user_id')
        
        if not automation_id:
            return create_enterprise_response(False, error="automation_id is required"), 400
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Execute automation
        result = await atom_workflow_automation_service.execute_automation(
            automation_id=automation_id,
            trigger_context=trigger_context,
            triggered_by=triggered_by
        )
        
        if result.get('ok'):
            return create_enterprise_response(
                True,
                data=result,
                message="Workflow automation executed successfully"
            )
        else:
            return create_enterprise_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Execute workflow automation error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/security', methods=['POST'])
@jwt_required()
@require_enterprise_role('security_admin')
@require_security_level(SecurityLevel.ENTERPRISE)
def create_security_automation():
    """Create security automation"""
    try:
        data = get_enterprise_request_data()
        security_event = data.get('security_event')
        automation_config = data.get('automation_config', {})
        user_id = data.get('user_id')
        
        if not security_event:
            return create_enterprise_response(False, error="security_event is required"), 400
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Create security automation
        result = await atom_workflow_automation_service.create_security_automation(security_event, automation_config)
        
        if result.get('ok'):
            return create_enterprise_response(
                True,
                data=result,
                message="Security automation created successfully"
            )
        else:
            return create_enterprise_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Create security automation error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/compliance', methods=['POST'])
@jwt_required()
@require_enterprise_role('compliance_admin')
@require_security_level(SecurityLevel.ENTERPRISE)
def create_compliance_automation():
    """Create compliance automation"""
    try:
        data = get_enterprise_request_data()
        compliance_violation = data.get('compliance_violation')
        automation_config = data.get('automation_config', {})
        user_id = data.get('user_id')
        
        if not compliance_violation:
            return create_enterprise_response(False, error="compliance_violation is required"), 400
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Create compliance automation
        result = await atom_workflow_automation_service.create_compliance_automation(compliance_violation, automation_config)
        
        if result.get('ok'):
            return create_enterprise_response(
                True,
                data=result,
                message="Compliance automation created successfully"
            )
        else:
            return create_enterprise_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Create compliance automation error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/integration', methods=['POST'])
@jwt_required()
@require_enterprise_role('integration_admin')
@require_security_level(SecurityLevel.ADVANCED)
def create_integration_automation():
    """Create integration automation"""
    try:
        data = get_enterprise_request_data()
        platform = data.get('platform')
        integration_config = data.get('integration_config', {})
        user_id = data.get('user_id')
        
        if not platform:
            return create_enterprise_response(False, error="platform is required"), 400
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Create integration automation
        result = await atom_workflow_automation_service.create_integration_automation(platform, integration_config)
        
        if result.get('ok'):
            return create_enterprise_response(
                True,
                data=result,
                message="Integration automation created successfully"
            )
        else:
            return create_enterprise_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Create integration automation error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/list', methods=['POST'])
@jwt_required()
@require_security_level(SecurityLevel.STANDARD)
def get_automations():
    """Get workflow automations"""
    try:
        data = get_enterprise_request_data()
        automation_type = data.get('automation_type')
        priority = data.get('priority')
        status = data.get('status')
        created_by = data.get('created_by')
        user_id = data.get('user_id')
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Get automations
        filters = {
            'automation_type': automation_type,
            'priority': priority,
            'status': status,
            'created_by': created_by
        }
        
        automations = await atom_workflow_automation_service.get_automations(filters)
        
        return create_enterprise_response(
            True,
            data={
                'automations': automations,
                'total_count': len(automations),
                'filters': filters
            },
            message="Automations retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get automations error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/executions', methods=['POST'])
@jwt_required()
@require_security_level(SecurityLevel.STANDARD)
def get_automation_executions():
    """Get automation executions"""
    try:
        data = get_enterprise_request_data()
        automation_id = data.get('automation_id')
        status = data.get('status')
        triggered_by = data.get('triggered_by')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Get executions
        filters = {
            'automation_id': automation_id,
            'status': status,
            'triggered_by': triggered_by,
            'date_from': date_from,
            'date_to': date_to
        }
        
        executions = await atom_workflow_automation_service.get_automation_executions(automation_id, filters)
        
        return create_enterprise_response(
            True,
            data={
                'executions': executions,
                'total_count': len(executions),
                'filters': filters
            },
            message="Automation executions retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get automation executions error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/automation/metrics', methods=['POST'])
@jwt_required()
@require_security_level(SecurityLevel.ADVANCED)
def get_automation_metrics():
    """Get automation metrics"""
    try:
        data = get_enterprise_request_data()
        time_range = data.get('time_range', 'last_30_days')
        include_details = data.get('include_details', False)
        
        if not atom_workflow_automation_service:
            return create_enterprise_response(False, error="Workflow automation service not available"), 503
        
        # Get automation metrics
        metrics = await atom_workflow_automation_service.get_automation_metrics()
        
        # Add additional details if requested
        if include_details:
            metrics['automations_by_type'] = {
                'security': len([a for a in atom_workflow_automation_service.automations.values() 
                               if a.automation_type == WorkflowAutomationType.SECURITY]),
                'compliance': len([a for a in atom_workflow_automation_service.automations.values() 
                                   if a.automation_type == WorkflowAutomationType.COMPLIANCE]),
                'integration': len([a for a in atom_workflow_automation_service.automations.values() 
                                    if a.automation_type == WorkflowAutomationType.INTEGRATION])
            }
        
        return create_enterprise_response(
            True,
            data={
                'metrics': metrics,
                'time_range': time_range,
                'include_details': include_details
            },
            message="Automation metrics retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get automation metrics error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

# Enterprise Integration Endpoints
@enterprise_bp.route('/integration/platforms/status', methods=['POST'])
@jwt_required()
@require_security_level(SecurityLevel.STANDARD)
def get_platform_integration_status():
    """Get platform integration status"""
    try:
        data = get_enterprise_request_data()
        platforms = data.get('platforms', ['slack', 'teams', 'google_chat', 'discord'])
        
        platform_status = {}
        
        for platform in platforms:
            integration = atom_workflow_automation_service.platform_integrations.get(platform)
            if integration:
                try:
                    status = await integration.get_service_status()
                    platform_status[platform] = {
                        'status': 'active',
                        'service_info': status,
                        'last_check': datetime.utcnow().isoformat()
                    }
                except Exception as e:
                    platform_status[platform] = {
                        'status': 'error',
                        'error': str(e),
                        'last_check': datetime.utcnow().isoformat()
                    }
            else:
                platform_status[platform] = {
                    'status': 'not_configured',
                    'last_check': datetime.utcnow().isoformat()
                }
        
        return create_enterprise_response(
            True,
            data={
                'platform_status': platform_status,
                'total_platforms': len(platforms),
                'active_platforms': len([s for s in platform_status.values() if s['status'] == 'active'])
            },
            message="Platform integration status retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get platform integration status error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/integration/workflows/sync', methods=['POST'])
@jwt_required()
@require_enterprise_role('integration_admin')
@require_security_level(SecurityLevel.ADVANCED)
def sync_integration_workflows():
    """Sync integration workflows"""
    try:
        data = get_enterprise_request_data()
        platforms = data.get('platforms', ['slack', 'teams', 'google_chat', 'discord'])
        sync_type = data.get('sync_type', 'full')
        user_id = data.get('user_id')
        
        sync_results = {}
        
        for platform in platforms:
            integration = atom_workflow_automation_service.platform_integrations.get(platform)
            if integration:
                try:
                    # Sync workflows for platform
                    if sync_type == 'full':
                        # Full sync including workspaces, channels, etc.
                        workspaces = await integration.get_intelligent_workspaces(user_id)
                        for workspace in workspaces:
                            channels = await integration.get_intelligent_channels(workspace['id'], user_id)
                            for channel in channels:
                                # Create integration automation for channel
                                automation_data = {
                                    'platform': platform,
                                    'workspace': workspace,
                                    'channel': channel
                                }
                                result = await atom_workflow_automation_service.create_integration_automation(platform, automation_data)
                                sync_results[platform] = sync_results.get(platform, [])
                                sync_results[platform].append(result)
                    
                    sync_results[platform] = {
                        'status': 'success',
                        'sync_type': sync_type,
                        'workspaces_synced': len(workspaces) if 'workspaces' in locals() else 0
                    }
                except Exception as e:
                    sync_results[platform] = {
                        'status': 'error',
                        'error': str(e),
                        'sync_type': sync_type
                    }
            else:
                sync_results[platform] = {
                    'status': 'not_configured',
                    'sync_type': sync_type
                }
        
        return create_enterprise_response(
            True,
            data={
                'sync_results': sync_results,
                'sync_type': sync_type,
                'platforms': platforms
            },
            message="Integration workflows synchronized successfully"
        )
    
    except Exception as e:
        logger.error(f"Sync integration workflows error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

# Enterprise Analytics and Monitoring
@enterprise_bp.route('/analytics/comprehensive', methods=['POST'])
@jwt_required()
@require_security_level(SecurityLevel.ADVANCED)
def get_comprehensive_analytics():
    """Get comprehensive enterprise analytics"""
    try:
        data = get_enterprise_request_data()
        time_range = data.get('time_range', 'last_30_days')
        metrics_type = data.get('metrics_type', 'all')
        include_ai = data.get('include_ai', True)
        user_id = data.get('user_id')
        
        analytics_data = {}
        
        # Security analytics
        if metrics_type in ['all', 'security'] and atom_enterprise_security_service:
            security_metrics = await atom_enterprise_security_service.get_security_metrics()
            analytics_data['security'] = {
                'metrics': security_metrics,
                'time_range': time_range,
                'ai_enhanced': include_ai
            }
        
        # Workflow automation analytics
        if metrics_type in ['all', 'automation'] and atom_workflow_automation_service:
            automation_metrics = await atom_workflow_automation_service.get_automation_metrics()
            analytics_data['automation'] = {
                'metrics': automation_metrics,
                'time_range': time_range,
                'ai_enhanced': include_ai
            }
        
        # AI analytics
        if include_ai and ai_enhanced_service:
            ai_metrics = await ai_enhanced_service.get_performance_metrics()
            analytics_data['ai'] = {
                'metrics': ai_metrics,
                'time_range': time_range,
                'ai_enhanced': True
            }
        
        # Platform integration analytics
        platform_analytics = {}
        for platform, integration in atom_workflow_automation_service.platform_integrations.items():
            if integration:
                try:
                    status = await integration.get_service_status()
                    platform_analytics[platform] = {
                        'status': status,
                        'active_users': status.get('active_users', 0),
                        'message_count': status.get('message_count', 0),
                        'uptime': status.get('uptime', 0)
                    }
                except Exception as e:
                    platform_analytics[platform] = {
                        'status': 'error',
                        'error': str(e)
                    }
        
        analytics_data['platforms'] = platform_analytics
        
        return create_enterprise_response(
            True,
            data={
                'analytics': analytics_data,
                'time_range': time_range,
                'metrics_type': metrics_type,
                'include_ai': include_ai
            },
            message="Comprehensive analytics retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get comprehensive analytics error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

@enterprise_bp.route('/monitoring/health', methods=['POST'])
def enterprise_health_monitoring():
    """Enterprise health monitoring with automation integration"""
    try:
        if not validate_enterprise_config():
            return create_enterprise_response(False, error="Enterprise configuration validation failed"), 500
        
        health_status = {
            'enterprise_security_service': atom_enterprise_security_service is not None,
            'enterprise_unified_service': atom_enterprise_unified_service is not None,
            'workflow_automation_service': atom_workflow_automation_service is not None,
            'ai_service': ai_enhanced_service is not None,
            'ai_integration': atom_ai_integration is not None
        }
        
        # Check service status
        all_healthy = all(health_status.values())
        
        # Get detailed status if services are available
        service_info = {}
        service_metrics = {}
        
        if atom_enterprise_security_service:
            service_info['security_service'] = await atom_enterprise_security_service.get_service_info()
            service_metrics['security_service'] = await atom_enterprise_security_service.get_security_metrics()
        
        if atom_enterprise_unified_service:
            service_info['unified_service'] = await atom_enterprise_unified_service.get_service_info()
            service_metrics['unified_service'] = await atom_enterprise_unified_service.get_enterprise_metrics()
        
        if atom_workflow_automation_service:
            service_info['automation_service'] = await atom_workflow_automation_service.get_service_info()
            service_metrics['automation_service'] = await atom_workflow_automation_service.get_automation_metrics()
        
        if ai_enhanced_service:
            service_info['ai_service'] = await ai_enhanced_service.get_service_info()
            service_metrics['ai_service'] = await ai_enhanced_service.get_performance_metrics()
        
        # Platform integration health
        platform_health = {}
        for platform, integration in atom_workflow_automation_service.platform_integrations.items():
            if integration:
                try:
                    status = await integration.get_service_status()
                    platform_health[platform] = {
                        'status': 'healthy' if status else 'unhealthy',
                        'last_check': datetime.utcnow().isoformat(),
                        'service_info': status
                    }
                except Exception as e:
                    platform_health[platform] = {
                        'status': 'unhealthy',
                        'error': str(e),
                        'last_check': datetime.utcnow().isoformat()
                    }
            else:
                platform_health[platform] = {
                    'status': 'not_configured',
                    'last_check': datetime.utcnow().isoformat()
                }
        
        # Active automations status
        automation_health = {
            'total_automations': len(atom_workflow_automation_service.automations) if atom_workflow_automation_service else 0,
            'active_automations': len([a for a in atom_workflow_automation_service.automations.values() 
                                      if a.status == AutomationStatus.ACTIVE]) if atom_workflow_automation_service else 0,
            'failed_automations': len([a for a in atom_workflow_automation_service.automations.values() 
                                      if a.status == AutomationStatus.FAILED]) if atom_workflow_automation_service else 0,
            'executed_today': atom_workflow_automation_service.automation_metrics['executed_today'] if atom_workflow_automation_service else 0
        }
        
        return create_enterprise_response(
            all_healthy,
            data={
                'services': health_status,
                'service_info': service_info,
                'service_metrics': service_metrics,
                'platform_health': platform_health,
                'automation_health': automation_health,
                'status': 'healthy' if all_healthy else 'degraded'
            },
            message="Enterprise services operational" if all_healthy else "Some enterprise services unavailable"
        )
    
    except Exception as e:
        logger.error(f"Enterprise health monitoring error: {e}")
        return create_enterprise_response(False, error=str(e)), 500

# Error handlers
@enterprise_bp.errorhandler(404)
def enterprise_not_found(error):
    return create_enterprise_response(False, error="Endpoint not found"), 404

@enterprise_bp.errorhandler(500)
def enterprise_internal_error(error):
    logger.error(f"Enterprise internal server error: {error}")
    return create_enterprise_response(False, error="Internal server error"), 500

# Helper functions
async def _verify_enterprise_credentials(username: str, password: str) -> Dict[str, Any]:
    """Verify enterprise credentials"""
    # Mock implementation - would use actual user database
    if username == 'admin' and password == 'EnterpriseAdmin123!':
        return {
            'user_id': 'enterprise_admin_001',
            'username': 'admin',
            'roles': ['admin', 'security_admin', 'workflow_admin', 'compliance_admin', 'automation_admin', 'integration_admin'],
            'security_level': 'enterprise',
            'permissions': ['all']
        }
    return None

# Register blueprint
def register_enterprise_api(app):
    """Register enterprise API blueprint"""
    app.register_blueprint(enterprise_bp)
    logger.info("Enterprise API blueprint registered")

# Export for external use
__all__ = [
    'enterprise_bp',
    'register_enterprise_api',
    'create_enterprise_response',
    'get_enterprise_request_data',
    'require_enterprise_role',
    'require_security_level'
]