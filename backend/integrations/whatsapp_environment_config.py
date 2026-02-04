"""
Environment Configuration for WhatsApp Business Integration
"""

import os
from typing import Any, Dict


def get_whatsapp_environment_config() -> Dict[str, Any]:
    """Get WhatsApp Business configuration from environment variables"""
    return {
        'production': {
            'access_token': os.getenv('WHATSAPP_ACCESS_TOKEN_PRODUCTION'),
            'phone_number_id': os.getenv('WHATSAPP_PHONE_NUMBER_ID_PRODUCTION'),
            'webhook_verify_token': os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN_PRODUCTION'),
            'webhook_url': os.getenv('WHATSAPP_WEBHOOK_URL_PRODUCTION'),
            'api_base_url': 'https://graph.facebook.com/v18.0',
        },
        'staging': {
            'access_token': os.getenv('WHATSAPP_ACCESS_TOKEN_STAGING'),
            'phone_number_id': os.getenv('WHATSAPP_PHONE_NUMBER_ID_STAGING'),
            'webhook_verify_token': os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN_STAGING'),
            'webhook_url': os.getenv('WHATSAPP_WEBHOOK_URL_STAGING'),
            'api_base_url': 'https://graph.facebook.com/v18.0',
        },
        'development': {
            'access_token': os.getenv('WHATSAPP_ACCESS_TOKEN_DEV'),
            'phone_number_id': os.getenv('WHATSAPP_PHONE_NUMBER_ID_DEV'),
            'webhook_verify_token': os.getenv('WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV'),
            'webhook_url': os.getenv('WHATSAPP_WEBHOOK_URL_DEV', 'http://localhost:5058/api/whatsapp/webhook'),
            'api_base_url': 'https://graph.facebook.com/v18.0',
        }
    }

def get_current_environment() -> str:
    """Get current environment from ENVIRONMENT variable"""
    return os.getenv('ENVIRONMENT', 'development').lower()

def get_whatsapp_config_for_current_env() -> Dict[str, Any]:
    """Get WhatsApp configuration for current environment"""
    env = get_current_environment()
    configs = get_whatsapp_environment_config()
    
    base_config = configs.get(env, configs['development'])
    
    # Add common configuration
    common_config = {
        'environment': env,
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
    }
    
    # Merge configurations
    return {**base_config, **common_config}

def validate_whatsapp_config(config: Dict[str, Any]) -> Dict[str, Any]:
    """Validate WhatsApp configuration and return validation results"""
    validation_result = {
        'is_valid': True,
        'errors': [],
        'warnings': [],
        'missing_required': [],
    }
    
    # Check required fields
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
    
    # Validate business hours
    if config.get('features', {}).get('business_hours_enabled'):
        start_time = config.get('features', {}).get('business_hours_start')
        end_time = config.get('features', {}).get('business_hours_end')
        
        if not start_time or not end_time:
            validation_result['warnings'].append('Business hours enabled but start or end time not set')
    
    # Validate database configuration
    db_config = config.get('database', {})
    required_db_fields = ['host', 'database', 'user']
    for field in required_db_fields:
        if not db_config.get(field):
            validation_result['errors'].append(f'Database field {field} is missing')
            validation_result['is_valid'] = False
    
    return validation_result

def get_whatsapp_config_with_validation() -> Dict[str, Any]:
    """Get WhatsApp configuration with validation"""
    config = get_whatsapp_config_for_current_env()
    validation = validate_whatsapp_config(config)
    
    return {
        'config': config,
        'validation': validation,
        'environment': get_current_environment(),
    }

if __name__ == '__main__':
    # Test configuration loading
    import json
    
    config_with_validation = get_whatsapp_config_with_validation()
    
    print(f"Environment: {config_with_validation['environment']}")
    print(f"Configuration valid: {config_with_validation['validation']['is_valid']}")
    
    if config_with_validation['validation']['errors']:
        print("\nErrors:")
        for error in config_with_validation['validation']['errors']:
            print(f"  - {error}")
    
    if config_with_validation['validation']['warnings']:
        print("\nWarnings:")
        for warning in config_with_validation['validation']['warnings']:
            print(f"  - {warning}")
    
    if config_with_validation['validation']['missing_required']:
        print("\nMissing Required Fields:")
        for field in config_with_validation['validation']['missing_required']:
            print(f"  - {field}")
    
    print(f"\nConfiguration (sensitive fields hidden):")
    safe_config = config_with_validation['config'].copy()
    if 'access_token' in safe_config:
        safe_config['access_token'] = '***HIDDEN***'
    print(json.dumps(safe_config, indent=2, default=str))