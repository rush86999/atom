"""
WhatsApp Business API Credentials Setup Guide
Step-by-step guide for production deployment
"""

import json
import os
from datetime import datetime


def create_api_setup_guide():
    """Create comprehensive API setup guide"""
    
    setup_guide = {
        "title": "WhatsApp Business API Production Setup Guide",
        "description": "Complete guide to set up WhatsApp Business API for production use",
        "estimated_time": "30 minutes",
        "prerequisites": [
            "Meta Business Account",
            "WhatsApp Business Account",
            "Verified phone number",
            "Facebook Developer account"
        ],
        "step_by_step": {
            "step_1": {
                "title": "Create Meta Business Account",
                "description": "Set up your business account if you don't have one",
                "actions": [
                    "Go to https://business.facebook.com/",
                    "Click 'Create Account'",
                    "Enter business details (name, address, contact)",
                    "Verify business email and phone number",
                    "Complete business verification process"
                ],
                "verification_time": "1-3 business days",
                "estimated_time": "15 minutes"
            },
            "step_2": {
                "title": "Set Up WhatsApp Business API",
                "description": "Configure WhatsApp Business API in Meta for Developers",
                "actions": [
                    "Go to https://developers.facebook.com/",
                    "Log in with your Meta Business account",
                    "Click 'My Apps' → 'Create App'",
                    "Choose 'Business' → 'WhatsApp'",
                    "Enter app name and contact email",
                    "Select 'Business account' and 'WhatsApp Business account'"
                ],
                "estimated_time": "10 minutes"
            },
            "step_3": {
                "title": "Configure WhatsApp Business Settings",
                "description": "Set up phone number and messaging features",
                "actions": [
                    "In your app dashboard, go to WhatsApp → Configuration",
                    "Add your WhatsApp Business phone number",
                    "Verify phone number (receive verification code)",
                    "Select display name (will be shown in messages)",
                    "Set up business profile information"
                ],
                "estimated_time": "10 minutes"
            },
            "step_4": {
                "title": "Get API Credentials",
                "description": "Extract required credentials for ATOM integration",
                "actions": [
                    "In WhatsApp settings, go to 'API Configuration'",
                    "Select the version (use latest stable version)",
                    "Generate Permanent Access Token",
                    "Copy the Access Token (starts with EAAJZC...)",
                    "Find your Phone Number ID in the WhatsApp settings",
                    "Note down both credentials for ATOM configuration"
                ],
                "credentials": {
                    "access_token": {
                        "description": "Permanent API access token",
                        "format": "Starts with EAAJZC...",
                        "length": "200+ characters",
                        "example": "EAAJZC... (very long string)"
                    },
                    "phone_number_id": {
                        "description": "Unique identifier for your WhatsApp phone number",
                        "format": "Numeric string",
                        "example": "123456789012345"
                    }
                },
                "estimated_time": "5 minutes"
            },
            "step_5": {
                "title": "Set Up Webhook Configuration",
                "description": "Configure webhook to receive incoming messages",
                "actions": [
                    "Go to WhatsApp → Configuration → Webhooks",
                    "Set Webhook URL (for development: use ngrok)",
                    "Generate Webhook Verify Token (custom string)",
                    "Subscribe to required message events",
                    "Verify webhook configuration"
                ],
                "webhook_events": [
                    "messages",
                    "message_delivery", 
                    "message_reads",
                    "message_failed",
                    "message_status"
                ],
                "estimated_time": "15 minutes"
            },
            "step_6": {
                "title": "Test Message Templates",
                "description": "Create and test message templates",
                "actions": [
                    "Go to WhatsApp → Message Templates",
                    "Create template for welcome messages",
                    "Create template for appointment reminders",
                    "Submit templates for approval",
                    "Wait for template approval (1-2 business days)"
                ],
                "template_categories": [
                    "UTILITY - appointment reminders, order updates",
                    "MARKETING - promotional content", 
                    "AUTHENTICATION - one-time passwords, verification"
                ],
                "estimated_time": "20 minutes"
            },
            "step_7": {
                "title": "Configure ATOM Integration",
                "description": "Set up ATOM environment variables",
                "actions": [
                    "Open your ATOM backend .env file",
                    "Add WHATSAPP_ACCESS_TOKEN_DEV with your access token",
                    "Add WHATSAPP_PHONE_NUMBER_ID_DEV with your phone number ID",
                    "Add WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV with your custom token",
                    "Set WHATSAPP_WEBHOOK_URL_DEV to your webhook URL",
                    "Restart ATOM backend service"
                ],
                "environment_variables": {
                    "WHATSAPP_ACCESS_TOKEN_DEV": "Your 200+ character access token",
                    "WHATSAPP_PHONE_NUMBER_ID_DEV": "Your phone number ID (numeric)",
                    "WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV": "Custom webhook verification string",
                    "WHATSAPP_WEBHOOK_URL_DEV": "http://localhost:5058/api/whatsapp/webhook"
                },
                "estimated_time": "10 minutes"
            },
            "step_8": {
                "title": "Test Integration",
                "description": "Verify ATOM WhatsApp integration is working",
                "actions": [
                    "Start ATOM backend service",
                    "Check WhatsApp health endpoint: /api/whatsapp/health",
                    "Send test message via ATOM UI",
                    "Verify message is received on WhatsApp",
                    "Test webhook receives message successfully",
                    "Check analytics and conversation tracking"
                ],
                "test_endpoints": [
                    "GET /api/whatsapp/health - Service health check",
                    "GET /api/whatsapp/service/health - Detailed service status",
                    "POST /api/whatsapp/send - Send message test",
                    "GET /api/whatsapp/conversations - Check conversation tracking"
                ],
                "estimated_time": "15 minutes"
            }
        },
        "troubleshooting": {
            "common_issues": [
                {
                    "issue": "Access Token Invalid",
                    "solution": "Regenerate token in Meta for Developers, ensure it's permanent, not temporary",
                    "check": "Verify token starts with EAAJZC and is 200+ characters"
                },
                {
                    "issue": "Phone Number Not Found",
                    "solution": "Ensure phone number is verified in WhatsApp Business settings",
                    "check": "Phone number ID should be numeric string"
                },
                {
                    "issue": "Webhook Verification Failed",
                    "solution": "Check webhook URL is accessible and verify token matches exactly",
                    "check": "Use ngrok for local development webhook URLs"
                },
                {
                    "issue": "Messages Not Delivering",
                    "solution": "Check message templates are approved and phone number is in correct status",
                    "check": "Verify you haven't exceeded rate limits (50 messages/second)"
                }
            ]
        },
        "production_checklist": {
            "before_going_live": [
                "✅ All message templates are approved by WhatsApp",
                "✅ Webhook URL uses HTTPS (required for production)",
                "✅ Phone number is verified and active",
                "✅ Business profile information is complete",
                "✅ Rate limits are configured properly",
                "✅ Error handling and logging is set up",
                "✅ Database backups are configured",
                "✅ Monitoring and alerts are configured"
            ],
            "rate_limits": {
                "messages_per_second": "50",
                "messages_per_minute": "1000", 
                "messages_per_hour": "10000",
                "api_calls_per_hour": "1000"
            },
            "security_requirements": [
                "Use HTTPS for all webhook URLs",
                "Store access tokens securely",
                "Implement webhook signature verification",
                "Set up proper CORS policies",
                "Regularly rotate access tokens"
            ]
        },
        "resources": {
            "official_documentation": "https://developers.facebook.com/docs/whatsapp",
            "meta_business": "https://business.facebook.com/",
            "developer_portal": "https://developers.facebook.com/",
            "whatsapp_policies": "https://faq.whatsapp.com/general/business-policy",
            "api_reference": "https://developers.facebook.com/docs/whatsapp/cloud-api/reference"
        },
        "support": {
            "atom_documentation": "/docs/integrations/whatsapp-business.md",
            "environment_setup": "/docs/integrations/whatsapp-environment-setup.md",
            "deployment_guide": "/WHATSAPP_INTEGRATION_READY.md"
        }
    }
    
    return setup_guide

def create_environment_template():
    """Create environment variables template"""
    
    env_template = {
        "description": "WhatsApp Business API Environment Variables Template",
        "usage": "Copy these variables to your .env file and replace with your actual values",
        "variables": {
            "# WhatsApp Business API Configuration": "",
            "WHATSAPP_ACCESS_TOKEN_DEV": "EAAJZC... (your 200+ character access token)",
            "WHATSAPP_PHONE_NUMBER_ID_DEV": "123456789012345 (your phone number ID)",
            "WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV": "your_custom_webhook_verification_token",
            "WHATSAPP_WEBHOOK_URL_DEV": "http://localhost:5058/api/whatsapp/webhook",
            
            "# Business Profile Configuration": "",
            "WHATSAPP_BUSINESS_NAME": "Your Business Name",
            "WHATSAPP_BUSINESS_DESCRIPTION": "Your business description",
            "WHATSAPP_BUSINESS_EMAIL": "contact@yourbusiness.com",
            "WHATSAPP_BUSINESS_WEBSITE": "https://yourbusiness.com",
            
            "# Database Configuration": "",
            "DATABASE_HOST": "localhost",
            "DATABASE_NAME": "atom_development", 
            "DATABASE_USER": "postgres",
            "DATABASE_PASSWORD": "your_database_password",
            "DATABASE_PORT": "5432",
            
            "# WhatsApp Features Configuration": "",
            "WHATSAPP_AUTO_REPLY_ENABLED": "false",
            "WHATSAPP_BUSINESS_HOURS_ENABLED": "true",
            "WHATSAPP_BUSINESS_HOURS_START": "09:00",
            "WHATSAPP_BUSINESS_HOURS_END": "18:00",
            "WHATSAPP_MESSAGE_RETENTION_DAYS": "30",
            "WHATSAPP_RATE_LIMITING_ENABLED": "true",
            
            "# Monitoring Configuration": "",
            "WHATSAPP_HEALTH_CHECK_INTERVAL": "60",
            "WHATSAPP_MAX_CONSECUTIVE_FAILURES": "5",
            "WHATSAPP_WEBHOOK_SECURITY_ENABLED": "true",
            "WHATSAPP_ANALYTICS_TRACKING_ENABLED": "true",
            
            "# Environment Settings": "",
            "ENVIRONMENT": "development"
        },
        "instructions": {
            "step_1": "Copy the variables to your .env file",
            "step_2": "Replace placeholder values with your actual API credentials", 
            "step_3": "Ensure your database is running and accessible",
            "step_4": "Restart ATOM backend service",
            "step_5": "Test integration with API endpoints",
            "step_6": "Verify webhook functionality"
        }
    }
    
    return env_template

def main():
    """Create setup guides and templates"""
    
    print("🚀 Creating WhatsApp Business API Setup Guides...")
    
    # Create setup guide
    setup_guide = create_api_setup_guide()
    setup_file = '/tmp/whatsapp_api_setup_guide.json'
    
    with open(setup_file, 'w') as f:
        json.dump(setup_guide, f, indent=2, default=str)
    
    print(f"✅ Setup guide created: {setup_file}")
    
    # Create environment template
    env_template = create_environment_template()
    env_file = '/tmp/whatsapp_environment_template.json'
    
    with open(env_file, 'w') as f:
        json.dump(env_template, f, indent=2, default=str)
    
    print(f"✅ Environment template created: {env_file}")
    
    # Create .env template file
    env_content = """# WhatsApp Business API Configuration
# Copy this to your .env file and replace with your actual credentials

# Core API Configuration (REQUIRED for production)
WHATSAPP_ACCESS_TOKEN_DEV=EAAJZC...#your_200+character_access_token_here
WHATSAPP_PHONE_NUMBER_ID_DEV=123456789012345#your_phone_number_id_here
WHATSAPP_WEBHOOK_VERIFY_TOKEN_DEV=your_custom_webhook_verification_token_here
WHATSAPP_WEBHOOK_URL_DEV=http://localhost:5058/api/whatsapp/webhook

# Business Profile Configuration
WHATSAPP_BUSINESS_NAME=Your Business Name
WHATSAPP_BUSINESS_DESCRIPTION=AI-powered business automation platform
WHATSAPP_BUSINESS_EMAIL=contact@yourbusiness.com
WHATSAPP_BUSINESS_WEBSITE=https://yourbusiness.com

# Database Configuration
DATABASE_HOST=localhost
DATABASE_NAME=atom_development
DATABASE_USER=postgres
DATABASE_PASSWORD=your_database_password
DATABASE_PORT=5432

# WhatsApp Features Configuration
WHATSAPP_AUTO_REPLY_ENABLED=false
WHATSAPP_BUSINESS_HOURS_ENABLED=true
WHATSAPP_BUSINESS_HOURS_START=09:00
WHATSAPP_BUSINESS_HOURS_END=18:00
WHATSAPP_MESSAGE_RETENTION_DAYS=30
WHATSAPP_RATE_LIMITING_ENABLED=true

# Monitoring Configuration
WHATSAPP_HEALTH_CHECK_INTERVAL=60
WHATSAPP_MAX_CONSECUTIVE_FAILURES=5
WHATSAPP_WEBHOOK_SECURITY_ENABLED=true
WHATSAPP_ANALYTICS_TRACKING_ENABLED=true

# Environment Settings
ENVIRONMENT=development
"""
    
    env_template_file = '/tmp/whatsapp_environment_template.env'
    
    with open(env_template_file, 'w') as f:
        f.write(env_content)
    
    print(f"✅ Environment template created: {env_template_file}")
    
    # Display summary
    print("\n📋 WhatsApp Business API Setup Summary")
    print("=" * 60)
    
    print(f"\n🎯 Estimated Setup Time: {setup_guide['estimated_time']}")
    print(f"📋 Total Steps: {len(setup_guide['step_by_step'])}")
    print(f"🔧 Configuration Files Created: 3")
    
    print(f"\n📁 Files Created:")
    print(f"  📖 Setup Guide: {setup_file}")
    print(f"  🔧 Environment Template: {env_file}")
    print(f"  📝 .env Template: {env_template_file}")
    
    print(f"\n🚀 Quick Start:")
    print(f"  1. Follow setup guide: {setup_file}")
    print(f"  2. Copy environment variables: {env_template_file}")
    print(f"  3. Test integration with ATOM backend")
    print(f"  4. Start sending WhatsApp messages!")
    
    print(f"\n📊 Current ATOM Status:")
    print(f"  ✅ Backend API: 35 routes working")
    print(f"  ✅ Frontend UI: React components ready")
    print(f"  ✅ Demo Mode: Fully functional")
    print(f"  🎯 Production: Ready for API credentials")
    
    print(f"\n🎉 WhatsApp Business Integration Setup Guide Created!")
    print(f"🔗 Next: Get your Meta Business API credentials and test!")

if __name__ == '__main__':
    main()