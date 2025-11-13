"""
WhatsApp Integration Routes
Enhanced API routes with production-ready features
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from flask import Blueprint, request, jsonify, current_app
from .whatsapp_service_manager import whatsapp_service_manager
from .whatsapp_business_integration import whatsapp_integration

logger = logging.getLogger(__name__)

# Create Flask blueprint
whatsapp_bp = Blueprint('whatsapp_enhanced', __name__, url_prefix='/api/whatsapp')

@whatsapp_bp.route('/service/initialize', methods=['POST'])
def initialize_service():
    """Initialize WhatsApp Business service"""
    try:
        result = whatsapp_service_manager.initialize_service()
        return jsonify(result), 200 if result.get('success') else 400
    except Exception as e:
        logger.error(f"Error initializing WhatsApp service: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@whatsapp_bp.route('/service/health', methods=['GET'])
def service_health():
    """Enhanced health check for WhatsApp service"""
    try:
        health_data = whatsapp_service_manager.health_check()
        status_code = 200 if health_data.get('status') == 'healthy' else 503
        return jsonify(health_data), status_code
    except Exception as e:
        logger.error(f"Error in WhatsApp health check: {str(e)}")
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@whatsapp_bp.route('/service/metrics', methods=['GET'])
def service_metrics():
    """Get comprehensive WhatsApp service metrics"""
    try:
        metrics = whatsapp_service_manager.get_service_metrics()
        return jsonify(metrics), 200
    except Exception as e:
        logger.error(f"Error getting WhatsApp metrics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e),
            'timestamp': datetime.now().isoformat()
        }), 500

@whatsapp_bp.route('/send/batch', methods=['POST'])
def send_batch_messages():
    """Send messages to multiple recipients (batch messaging)"""
    try:
        data = request.get_json()
        
        # Validate input
        recipients = data.get('recipients', [])
        message = data.get('message', {})
        message_type = data.get('type', 'text')
        delay_between_messages = data.get('delay_between_messages', 1)  # seconds
        
        if not recipients or not message:
            return jsonify({
                'success': False,
                'error': 'Recipients and message are required'
            }), 400
        
        if len(recipients) > 100:
            return jsonify({
                'success': False,
                'error': 'Maximum 100 recipients per batch'
            }), 400
        
        results = []
        success_count = 0
        failure_count = 0
        
        for i, recipient in enumerate(recipients):
            try:
                # Add delay between messages to avoid rate limiting
                if i > 0 and delay_between_messages > 0:
                    import time
                    time.sleep(delay_between_messages)
                
                result = whatsapp_integration.send_message(
                    to=recipient,
                    message_type=message_type,
                    content=message
                )
                
                results.append({
                    'recipient': recipient,
                    'success': result.get('success', False),
                    'message_id': result.get('message_id'),
                    'error': result.get('error')
                })
                
                if result.get('success'):
                    success_count += 1
                else:
                    failure_count += 1
                    
            except Exception as e:
                results.append({
                    'recipient': recipient,
                    'success': False,
                    'error': str(e)
                })
                failure_count += 1
        
        return jsonify({
            'success': success_count > 0,
            'batch_id': f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            'total_recipients': len(recipients),
            'success_count': success_count,
            'failure_count': failure_count,
            'success_rate': (success_count / len(recipients)) * 100,
            'results': results,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error in batch message sending: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@whatsapp_bp.route('/conversations/search', methods=['GET'])
def search_conversations():
    """Search conversations by various criteria"""
    try:
        # Get search parameters
        query = request.args.get('query', '').strip()
        status = request.args.get('status', '')
        date_from = request.args.get('date_from')
        date_to = request.args.get('date_to')
        limit = min(int(request.args.get('limit', 50)), 100)  # Max 100 results
        offset = int(request.args.get('offset', 0))
        
        if not query and not status and not date_from and not date_to:
            return jsonify({
                'success': False,
                'error': 'At least one search parameter is required'
            }), 400
        
        # Get all conversations and filter (in production, this would be database query)
        conversations = whatsapp_integration.get_conversations(limit=500, offset=0)
        filtered_conversations = []
        
        for conv in conversations:
            # Text search in name or phone number
            if query:
                search_text = f"{conv.get('name', '')} {conv.get('phone_number', '')}".lower()
                if query.lower() not in search_text:
                    continue
            
            # Status filter
            if status and conv.get('status', '').lower() != status.lower():
                continue
            
            # Date range filter
            if date_from or date_to:
                try:
                    last_msg_date = datetime.fromisoformat(conv.get('last_message_at', '').replace('Z', '+00:00'))
                    
                    if date_from:
                        date_from_dt = datetime.fromisoformat(date_from)
                        if last_msg_date < date_from_dt:
                            continue
                    
                    if date_to:
                        date_to_dt = datetime.fromisoformat(date_to)
                        if last_msg_date > date_to_dt:
                            continue
                except (ValueError, TypeError):
                    continue
            
            filtered_conversations.append(conv)
        
        # Apply pagination
        total_count = len(filtered_conversations)
        paginated_results = filtered_conversations[offset:offset + limit]
        
        return jsonify({
            'success': True,
            'conversations': paginated_results,
            'pagination': {
                'total': total_count,
                'offset': offset,
                'limit': limit,
                'has_more': offset + limit < total_count
            },
            'search_criteria': {
                'query': query,
                'status': status,
                'date_from': date_from,
                'date_to': date_to
            },
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error searching conversations: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@whatsapp_bp.route('/templates/preview', methods=['POST'])
def preview_template():
    """Preview a message template before sending"""
    try:
        data = request.get_json()
        
        template_name = data.get('template_name')
        language_code = data.get('language_code', 'en')
        parameters = data.get('parameters', {})
        
        if not template_name:
            return jsonify({
                'success': False,
                'error': 'Template name is required'
            }), 400
        
        # In production, this would fetch template from database
        # For now, return a mock preview
        template_examples = {
            'appointment_reminder': {
                'body': 'Hello {{1}}, your appointment is scheduled for {{2}}.',
                'parameters': ['customer_name', 'appointment_time']
            },
            'welcome_message': {
                'body': 'Welcome to {{1}}! We\'re excited to help you with {{2}}.',
                'parameters': ['business_name', 'service']
            },
            'follow_up': {
                'body': 'Hi {{1}}, just checking in about your recent inquiry regarding {{2}}.',
                'parameters': ['customer_name', 'inquiry_type']
            }
        }
        
        template = template_examples.get(template_name, {
            'body': f'Template {template_name} with parameters {parameters}'
        })
        
        # Substitute parameters
        preview_text = template['body']
        for param, value in parameters.items():
            preview_text = preview_text.replace(f'{{{{{param}}}}}', str(value))
        
        return jsonify({
            'success': True,
            'template_name': template_name,
            'language_code': language_code,
            'preview': preview_text,
            'original_body': template['body'],
            'parameters_used': parameters,
            'timestamp': datetime.now().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error previewing template: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@whatsapp_bp.route('/analytics/export', methods=['GET'])
def export_analytics():
    """Export analytics data in various formats"""
    try:
        format_type = request.args.get('format', 'json')
        start_date = request.args.get('start_date')
        end_date = request.args.get('end_date')
        
        if not start_date or not end_date:
            return jsonify({
                'success': False,
                'error': 'Start date and end date are required'
            }), 400
        
        # Parse dates
        try:
            start_dt = datetime.fromisoformat(start_date)
            end_dt = datetime.fromisoformat(end_date)
        except ValueError:
            return jsonify({
                'success': False,
                'error': 'Invalid date format. Use ISO format (YYYY-MM-DDTHH:MM:SS)'
            }), 400
        
        # Get analytics data
        analytics = whatsapp_integration.get_analytics(start_dt, end_dt)
        
        # Format based on requested type
        if format_type == 'csv':
            import csv
            import io
            
            output = io.StringIO()
            writer = csv.writer(output)
            
            # Write CSV headers
            writer.writerow(['Type', 'Direction', 'Status', 'Count'])
            
            # Write data
            for stat in analytics.get('message_statistics', []):
                writer.writerow([
                    stat.get('message_type', ''),
                    stat.get('direction', ''),
                    stat.get('status', ''),
                    stat.get('count', 0)
                ])
            
            csv_data = output.getvalue()
            output.close()
            
            from flask import Response
            return Response(
                csv_data,
                mimetype='text/csv',
                headers={'Content-Disposition': f'attachment; filename=whatsapp_analytics_{start_date}_{end_date}.csv'}
            )
        
        elif format_type == 'excel':
            # Excel export would require openpyxl or similar library
            return jsonify({
                'success': False,
                'error': 'Excel export not implemented yet'
            }), 501
        
        else:  # Default to JSON
            return jsonify({
                'success': True,
                'format': format_type,
                'date_range': {
                    'start': start_date,
                    'end': end_date
                },
                'analytics': analytics,
                'export_timestamp': datetime.now().isoformat()
            })
        
    except Exception as e:
        logger.error(f"Error exporting analytics: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@whatsapp_bp.route('/configuration/business-profile', methods=['GET', 'PUT'])
def business_profile():
    """Get or update WhatsApp business profile"""
    try:
        if request.method == 'GET':
            # Return current business profile configuration
            profile = whatsapp_service_manager.config.get('business_profile', {})
            return jsonify({
                'success': True,
                'business_profile': profile,
                'timestamp': datetime.now().isoformat()
            })
        
        elif request.method == 'PUT':
            # Update business profile
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
            
            # Update configuration (in production, this would update database)
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
        logger.error(f"Error managing business profile: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@whatsapp_bp.route('/webhooks/test', methods=['POST'])
def test_webhook():
    """Test webhook configuration"""
    try:
        data = request.get_json()
        test_url = data.get('webhook_url')
        verify_token = data.get('verify_token')
        
        if not test_url:
            return jsonify({
                'success': False,
                'error': 'Webhook URL is required'
            }), 400
        
        # Test webhook connectivity
        import requests
        import urllib.parse
        
        # Test webhook verification
        webhook_params = {
            'hub.mode': 'subscribe',
            'hub.verify_token': verify_token,
            'hub.challenge': 'test_challenge_12345'
        }
        
        try:
            response = requests.get(test_url, params=webhook_params, timeout=10)
            
            if response.status_code == 200:
                return jsonify({
                    'success': True,
                    'status': 'working',
                    'message': 'Webhook is properly configured and responding',
                    'test_time': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'success': False,
                    'status': 'failed',
                    'error': f'Webhook returned status {response.status_code}',
                    'response_text': response.text[:200]
                })
                
        except requests.exceptions.RequestException as e:
            return jsonify({
                'success': False,
                'status': 'failed',
                'error': f'Could not reach webhook: {str(e)}'
            })
    
    except Exception as e:
        logger.error(f"Error testing webhook: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

# Error handlers
@whatsapp_bp.errorhandler(429)
def ratelimit_handler(e):
    """Handle rate limiting errors"""
    return jsonify({
        'success': False,
        'error': 'Rate limit exceeded. Please try again later.',
        'retry_after': str(e.retry_after) if hasattr(e, 'retry_after') else '60',
        'timestamp': datetime.now().isoformat()
    }), 429

@whatsapp_bp.errorhandler(500)
def internal_error(e):
    """Handle internal server errors"""
    logger.error(f"Internal server error in WhatsApp API: {str(e)}")
    return jsonify({
        'success': False,
        'error': 'Internal server error',
        'timestamp': datetime.now().isoformat()
    }), 500