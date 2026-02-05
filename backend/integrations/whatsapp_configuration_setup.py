"""
WhatsApp Business Configuration Setup
Automated configuration setup for WhatsApp Business integration
"""

from datetime import datetime
import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

def setup_demo_configuration() -> Dict[str, Any]:
    """Set up demo configuration for testing without real API credentials"""
    return {
        'access_token': 'demo_token_' + 'x' * 100,  # Demo token
        'phone_number_id': '123456789012345',  # Demo phone ID
        'webhook_verify_token': 'demo_verify_token_atom_' + 'x' * 20,
        'webhook_url': 'http://localhost:5058/api/whatsapp/webhook',
        'environment': 'development',
        'is_demo': True,
        'database': {
            'host': 'localhost',
            'database': 'atom_development',
            'user': 'postgres',
            'password': '',
            'port': '5432',
        },
        'business_profile': {
            'name': 'ATOM AI Assistant (Demo)',
            'description': 'AI-powered business automation platform - Demo Mode',
            'email': 'demo@atom.ai',
            'website': 'https://atom.ai',
            'address': '123 Demo Street, Silicon Valley, CA 94000',
            'phone': '+1-555-ATM-DEMO',
        },
        'features': {
            'auto_reply_enabled': False,
            'business_hours_enabled': True,
            'business_hours_start': '09:00',
            'business_hours_end': '18:00',
            'message_retention_days': 30,
            'rate_limiting_enabled': True,
            'webhook_security_enabled': True,
            'analytics_tracking_enabled': True,
        },
        'monitoring': {
            'health_check_interval': 60,
            'max_consecutive_failures': 5,
            'alert_webhook': '',
        },
        'rate_limits': {
            'messages_per_second': 50,
            'messages_per_minute': 1000,
            'messages_per_hour': 10000,
            'api_calls_per_hour': 1000,
        },
        'status': 'demo_configured'
    }

def get_or_create_configuration() -> Dict[str, Any]:
    """Get configuration from environment or create demo config"""
    try:
        # Try to load from environment variables first
        config = {
            'access_token': os.getenv('WHATSAPP_ACCESS_TOKEN_DEV'),
            'phone_number_id': os.getenv('WHATSAPP_PHONE_NUMBER_ID_DEV'),
            'webhook_verify_token': os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV'),
            'webhook_url': os.getenv('WHATSAPP_WEBHOOK_URL_DEV', 'http://localhost:5058/api/whatsapp/webhook'),
            'environment': os.getenv('ENVIRONMENT', 'development'),
        }
        
        # Check if we have required configuration
        if config['access_token'] and config['phone_number_id']:
            # Add additional configuration
            config.update({
                'database': {
                    'host': os.getenv('DATABASE_HOST', 'localhost'),
                    'database': os.getenv('DATABASE_NAME', 'atom_development'),
                    'user': os.getenv('DATABASE_USER', 'postgres'),
                    'password': os.getenv('DATABASE_PASSWORD', ''),
                    'port': os.getenv('DATABASE_PORT', '5432'),
                },
                'business_profile': {
                    'name': os.getenv('WHATSAPP_BUSINESS_NAME', 'ATOM AI Assistant'),
                    'description': os.getenv('WHATSAPP_BUSINESS_DESCRIPTION', 'AI-powered business automation platform'),
                    'email': os.getenv('WHATSAPP_BUSINESS_EMAIL', 'support@atom.ai'),
                    'website': os.getenv('WHATSAPP_BUSINESS_WEBSITE', 'https://atom.ai'),
                    'address': os.getenv('WHATSAPP_BUSINESS_ADDRESS', ''),
                    'phone': os.getenv('WHATSAPP_BUSINESS_PHONE', ''),
                },
                'features': {
                    'auto_reply_enabled': os.getenv('WHATSAPP_AUTO_REPLY_ENABLED', 'false').lower() == 'true',
                    'business_hours_enabled': os.getenv('WHATSAPP_BUSINESS_HOURS_ENABLED', 'true').lower() == 'true',
                    'business_hours_start': os.getenv('WHATSAPP_BUSINESS_HOURS_START', '09:00'),
                    'business_hours_end': os.getenv('WHATSAPP_BUSINESS_HOURS_END', '18:00'),
                    'message_retention_days': int(os.getenv('WHATSAPP_MESSAGE_RETENTION_DAYS', '30')),
                    'rate_limiting_enabled': os.getenv('WHATSAPP_RATE_LIMITING_ENABLED', 'true').lower() == 'true',
                    'webhook_security_enabled': os.getenv('WHATSAPP_WEBHOOK_SECURITY_ENABLED', 'true').lower() == 'true',
                    'analytics_tracking_enabled': os.getenv('WHATSAPP_ANALYTICS_TRACKING_ENABLED', 'true').lower() == 'true',
                },
                'monitoring': {
                    'health_check_interval': int(os.getenv('WHATSAPP_HEALTH_CHECK_INTERVAL', '60')),
                    'max_consecutive_failures': int(os.getenv('WHATSAPP_MAX_CONSECUTIVE_FAILURES', '5')),
                    'alert_webhook': os.getenv('WHATSAPP_ALERT_WEBHOOK', ''),
                },
                'rate_limits': {
                    'messages_per_second': int(os.getenv('WHATSAPP_MESSAGES_PER_SECOND', '50')),
                    'messages_per_minute': int(os.getenv('WHATSAPP_MESSAGES_PER_MINUTE', '1000')),
                    'messages_per_hour': int(os.getenv('WHATSAPP_MESSAGES_PER_HOUR', '10000')),
                    'api_calls_per_hour': int(os.getenv('WHATSAPP_API_CALLS_PER_HOUR', '1000')),
                },
                'is_demo': False,
                'status': 'configured'
            })
            
            logger.info("WhatsApp configuration loaded from environment variables")
            return config
        
        else:
            # Fall back to demo configuration
            logger.warning("Missing required WhatsApp configuration, using demo mode")
            demo_config = setup_demo_configuration()
            
            # Save demo configuration for reference
            demo_file = '/tmp/whatsapp_demo_config.json'
            with open(demo_file, 'w') as f:
                json.dump(demo_config, f, indent=2, default=str)
            
            logger.info(f"Demo configuration saved to {demo_file}")
            return demo_config
            
    except Exception as e:
        logger.error(f"Error creating WhatsApp configuration: {str(e)}")
        # Return demo configuration as fallback
        return setup_demo_configuration()

def validate_configuration(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate configuration and return validation results"""
    validation_result = {
        'is_valid': True,
        'is_demo': config.get('is_demo', False),
        'errors': [],
        'warnings': [],
        'missing_required': [],
        'configuration_type': 'unknown'
    }
    
    # Check if it's demo configuration
    if config.get('is_demo'):
        validation_result['is_valid'] = True
        validation_result['configuration_type'] = 'demo'
        validation_result['warnings'].append('Using demo configuration for testing')
        return validation_result
    
    # Check required fields for production
    required_fields = ['access_token', 'phone_number_id']
    for field in required_fields:
        if not config.get(field):
            validation_result['is_valid'] = False
            validation_result['missing_required'].append(field)
            validation_result['errors'].append(f'Required field {field} is missing')
    
    # Check optional but recommended fields
    recommended_fields = ['webhook_verify_token', 'webhook_url']
    for field in recommended_fields:
        if not config.get(field):
            validation_result['warnings'].append(f'Recommended field {field} is missing')
    
    # Determine configuration type
    if validation_result['is_valid'] and not validation_result['missing_required']:
        validation_result['configuration_type'] = 'production'
    else:
        validation_result['configuration_type'] = 'incomplete'
    
    return validation_result

def setup_configuration_file() -> None:
    """Create a comprehensive configuration file for reference"""
    try:
        config_data = {
            "description": "WhatsApp Business Integration Configuration",
            "environment_variables": {
                "WHATSAPP_ACCESS_TOKEN_DEV": "Your Meta Business Access Token (200+ characters)",
                "WHATSAPP_PHONE_NUMBER_ID_DEV": "Your WhatsApp Phone Number ID from Meta Business",
                "WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV": "Custom webhook verification token",
                "WHATSAPP_WEBHOOK_URL_DEV": "http://localhost:5058/api/whatsapp/webhook",
                "ENVIRONMENT": "development"
            },
            "production_variables": {
                "WHATSAPP_ACCESS_TOKEN_PRODUCTION": "Production access token",
                "WHATSAPP_PHONE_NUMBER_ID_PRODUCTION": "Production phone number ID",
                "WHATSAPP_WEBHOOK_VERIFY_TOKEN_PRODUCTION": "Production webhook token",
                "WHATSAPP_WEBHOOK_URL_PRODUCTION": "https://your-domain.com/api/whatsapp/webhook"
            },
            "setup_instructions": {
                "step_1": "Create Meta Business Account at business.facebook.com",
                "step_2": "Set up WhatsApp Business API in Meta for Developers",
                "step_3": "Get Access Token and Phone Number ID",
                "step_4": "Configure webhook URL in WhatsApp Business settings",
                "step_5": "Set environment variables and restart server"
            },
            "demo_mode": {
                "enabled": True,
                "description": "Demo mode allows testing UI and API without real credentials",
                "limitations": [
                    "Messages are not actually sent",
                    "Webhook receives test data only",
                    "Analytics returns mock data"
                ]
            }
        }
        
        config_file = '/tmp/whatsapp_configuration_guide.json'
        with open(config_file, 'w') as f:
            json.dump(config_data, f, indent=2)
        
        logger.info(f"Configuration guide saved to {config_file}")
        
    except Exception as e:
        logger.error(f"Error creating configuration file: {str(e)}")

def initialize_configuration_system() -> Dict[str, Any]:
    """Initialize the complete configuration system"""
    try:
        # Create configuration guide
        setup_configuration_file()
        
        # Get or create configuration
        config = get_or_create_configuration()
        
        # Validate configuration
        validation = validate_configuration(config)
        
        result = {
            'config': config,
            'validation': validation,
            'timestamp': datetime.now().isoformat(),
            'setup_complete': True
        }
        
        # Log configuration status
        if validation['is_demo']:
            logger.info("WhatsApp Business initialized in DEMO mode")
            print("🎭 WhatsApp Business running in DEMO mode")
        elif validation['is_valid']:
            logger.info("WhatsApp Business initialized with valid configuration")
            print("✅ WhatsApp Business initialized with valid configuration")
        else:
            logger.warning(f"WhatsApp Business configuration incomplete: {validation['missing_required']}")
            print("⚠️  WhatsApp Business configuration incomplete")
        
        return result
        
    except Exception as e:
        logger.error(f"Error initializing configuration system: {str(e)}")
        error_result = {
            'config': setup_demo_configuration(),
            'validation': {'is_valid': False, 'is_demo': True, 'errors': [str(e)]},
            'timestamp': datetime.now().isoformat(),
            'setup_complete': False
        }
        return error_result

if __name__ == '__main__':
    # Test configuration system
    result = initialize_configuration_system()
    
    print(f"\n📊 Configuration Status:")
    print(f"Type: {result['validation']['configuration_type']}")
    print(f"Valid: {result['validation']['is_valid']}")
    print(f"Demo: {result['validation']['is_demo']}")
    
    if result['validation']['errors']:
        print(f"\n❌ Errors:")
        for error in result['validation']['errors']:
            print(f"  - {error}")
    
    if result['validation']['warnings']:
        print(f"\n⚠️  Warnings:")
        for warning in result['validation']['warnings']:
            print(f"  - {warning}")
    
    print(f"\n📝 Configuration file: /tmp/whatsapp_configuration_guide.json")
    print(f"🎭 Demo config file: /tmp/whatsapp_demo_config.json")