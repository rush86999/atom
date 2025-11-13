"""
WhatsApp Business Flask App Registration
Simplified Flask app integration for WhatsApp Business API
"""

from flask import Flask, jsonify, request
import logging
from datetime import datetime, timedelta
import json
from typing import Dict, Any

# Try to import WhatsApp components
try:
    from integrations.whatsapp_service_manager import whatsapp_service_manager
    from integrations.whatsapp_business_integration import whatsapp_integration
    WHATSAPP_AVAILABLE = True
except ImportError as e:
    logging.warning(f"WhatsApp Business integration not available: {e}")
    WHATSAPP_AVAILABLE = False

logger = logging.getLogger(__name__)

def register_whatsapp_routes(app: Flask):
    """Register WhatsApp Business routes with Flask app"""
    if not WHATSAPP_AVAILABLE:
        logger.warning("WhatsApp Business integration not available for registration")
        return False
    
    try:
        # Basic WhatsApp health check
        @app.route('/api/whatsapp/health', methods=['GET'])
        def whatsapp_health():
            try:
                if whatsapp_service_manager.config:
                    return jsonify({
                        'status': 'healthy',
                        'service': 'WhatsApp Business API',
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'status': 'not_configured',
                        'service': 'WhatsApp Business API'
                    }), 503
            except Exception as e:
                logger.error(f"WhatsApp health check error: {str(e)}")
                return jsonify({
                    'status': 'error',
                    'error': str(e)
                }), 500
        
        # Enhanced WhatsApp service health
        @app.route('/api/whatsapp/service/health', methods=['GET'])
        def whatsapp_service_health():
            try:
                health_data = whatsapp_service_manager.health_check()
                status_code = 200 if health_data.get('status') == 'healthy' else 503
                return jsonify(health_data), status_code
            except Exception as e:
                logger.error(f"WhatsApp service health check error: {str(e)}")
                return jsonify({
                    'status': 'unhealthy',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        # Enhanced WhatsApp service metrics
        @app.route('/api/whatsapp/service/metrics', methods=['GET'])
        def whatsapp_service_metrics():
            try:
                metrics = whatsapp_service_manager.get_service_metrics()
                return jsonify(metrics), 200
            except Exception as e:
                logger.error(f"WhatsApp service metrics error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        # Initialize WhatsApp service
        @app.route('/api/whatsapp/service/initialize', methods=['POST'])
        def initialize_whatsapp_service():
            try:
                result = whatsapp_service_manager.initialize_service()
                return jsonify(result), 200 if result.get('success') else 400
            except Exception as e:
                logger.error(f"WhatsApp service initialization error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }), 500
        
        # Send WhatsApp message
        @app.route('/api/whatsapp/send', methods=['POST'])
        def send_whatsapp_message():
            try:
                data = request.get_json()
                
                if not all(k in data for k in ['to', 'type', 'content']):
                    return jsonify({
                        'success': False,
                        'error': 'Missing required fields: to, type, content'
                    }), 400
                
                result = whatsapp_integration.send_message(
                    to=data['to'],
                    message_type=data['type'],
                    content=data['content']
                )
                
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"WhatsApp send message error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # Get WhatsApp conversations
        @app.route('/api/whatsapp/conversations', methods=['GET'])
        def get_whatsapp_conversations():
            try:
                limit = int(request.args.get('limit', 50))
                offset = int(request.args.get('offset', 0))
                
                conversations = whatsapp_integration.get_conversations(limit, offset)
                
                return jsonify({
                    'success': True,
                    'conversations': conversations,
                    'total': len(conversations)
                })
                
            except Exception as e:
                logger.error(f"WhatsApp conversations error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # Get WhatsApp messages
        @app.route('/api/whatsapp/messages/<whatsapp_id>', methods=['GET'])
        def get_whatsapp_messages(whatsapp_id):
            try:
                limit = int(request.args.get('limit', 100))
                
                messages = whatsapp_integration.get_messages(whatsapp_id, limit)
                
                return jsonify({
                    'success': True,
                    'messages': messages,
                    'total': len(messages)
                })
                
            except Exception as e:
                logger.error(f"WhatsApp messages error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # Create WhatsApp template
        @app.route('/api/whatsapp/templates', methods=['POST'])
        def create_whatsapp_template():
            try:
                data = request.get_json()
                
                if not all(k in data for k in ['template_name', 'category', 'language_code', 'components']):
                    return jsonify({
                        'success': False,
                        'error': 'Missing required fields: template_name, category, language_code, components'
                    }), 400
                
                result = whatsapp_integration.create_template(
                    template_name=data['template_name'],
                    category=data['category'],
                    language_code=data['language_code'],
                    components=data['components']
                )
                
                return jsonify(result)
                
            except Exception as e:
                logger.error(f"WhatsApp template creation error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # Get WhatsApp analytics
        @app.route('/api/whatsapp/analytics', methods=['GET'])
        def get_whatsapp_analytics():
            try:
                start_date = request.args.get('start_date')
                end_date = request.args.get('end_date')
                
                if start_date:
                    start_date = datetime.fromisoformat(start_date)
                else:
                    start_date = datetime.now() - timedelta(days=30)
                    
                if end_date:
                    end_date = datetime.fromisoformat(end_date)
                else:
                    end_date = datetime.now()
                
                analytics = whatsapp_integration.get_analytics(start_date, end_date)
                
                return jsonify({
                    'success': True,
                    'analytics': analytics,
                    'period': {
                        'start_date': start_date.isoformat(),
                        'end_date': end_date.isoformat()
                    }
                })
                
            except Exception as e:
                logger.error(f"WhatsApp analytics error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        # WhatsApp webhook
        @app.route('/api/whatsapp/webhook', methods=['GET', 'POST'])
        def whatsapp_webhook():
            try:
                if request.method == 'GET':
                    # Webhook verification
                    mode = request.args.get('hub.mode')
                    token = request.args.get('hub.verify_token')
                    challenge = request.args.get('hub.challenge')
                    
                    # For development, accept any token if mode is subscribe
                    if mode == 'subscribe':
                        return challenge, 200
                    else:
                        return "Verification failed", 403
                        
                else:  # POST
                    # Handle incoming messages and events
                    data = request.get_json()
                    logger.info(f"WhatsApp webhook received: {str(data)[:200]}...")
                    
                    # In a real implementation, process incoming messages here
                    # For now, just acknowledge receipt
                    
                    return "ok", 200
                    
            except Exception as e:
                logger.error(f"WhatsApp webhook error: {str(e)}")
                return "error", 500
        
        # Business profile management
        @app.route('/api/whatsapp/configuration/business-profile', methods=['GET', 'PUT'])
        def whatsapp_business_profile():
            try:
                if request.method == 'GET':
                    profile = whatsapp_service_manager.config.get('business_profile', {})
                    return jsonify({
                        'success': True,
                        'business_profile': profile,
                        'timestamp': datetime.now().isoformat()
                    })
                
                elif request.method == 'PUT':
                    data = request.get_json()
                    profile_updates = data.get('business_profile', {})
                    
                    # Validate profile data
                    required_fields = ['name', 'description', 'email']
                    missing_fields = [field for field in required_fields if not profile_updates.get(field)]
                    
                    if missing_fields:
                        return jsonify({
                            'success': False,
                            'error': f'Missing required fields: {missing_fields}'
                        }), 400
                    
                    # Update configuration
                    current_profile = whatsapp_service_manager.config.get('business_profile', {})
                    current_profile.update(profile_updates)
                    whatsapp_service_manager.config['business_profile'] = current_profile
                    
                    return jsonify({
                        'success': True,
                        'business_profile': current_profile,
                        'updated_fields': list(profile_updates.keys()),
                        'timestamp': datetime.now().isoformat()
                    })
            
            except Exception as e:
                logger.error(f"WhatsApp business profile error: {str(e)}")
                return jsonify({
                    'success': False,
                    'error': str(e)
                }), 500
        
        logger.info("WhatsApp Business routes registered successfully")
        return True
        
    except Exception as e:
        logger.error(f"Failed to register WhatsApp Business routes: {str(e)}")
        return False

def initialize_whatsapp_service(app: Flask):
    """Initialize WhatsApp service with Flask app"""
    if not WHATSAPP_AVAILABLE:
        logger.warning("WhatsApp Business integration not available for initialization")
        return False
    
    try:
        # Try to initialize service
        config = whatsapp_service_manager.load_configuration()
        init_success = whatsapp_service_manager.initialize_service()
        
        if init_success.get('success'):
            logger.info("WhatsApp Business service initialized successfully")
            return True
        else:
            logger.warning(f"WhatsApp Business service initialization failed: {init_success.get('error')}")
            return False
            
    except Exception as e:
        logger.error(f"Failed to initialize WhatsApp Business service: {str(e)}")
        return False