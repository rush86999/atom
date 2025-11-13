#!/usr/bin/env python3
"""
🚀 ATOM Integration Registration Fix
Fixes 404 errors by properly registering all integration blueprints
"""

import os
import sys
import logging
from pathlib import Path

# Add the backend/integrations directory to Python path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'integrations'))

logger = logging.getLogger(__name__)

class IntegrationRegistry:
    """Registry for all ATOM integrations"""
    
    def __init__(self):
        self.integrations = {}
        self.oauth_handlers = {}
        self.services = {}
        
    def register_integration(self, name, config):
        """Register an integration with the app"""
        self.integrations[name] = config
        
    def register_oauth_handler(self, name, handler_config):
        """Register an OAuth handler"""
        self.oauth_handlers[name] = handler_config
        
    def register_service(self, name, service_config):
        """Register a service"""
        self.services[name] = service_config

# Global integration registry
integration_registry = IntegrationRegistry()

def register_all_integrations(app):
    """
    Register all integration blueprints with the Flask app
    This fixes the 404 errors by properly registering all routes
    """
    
    logging.info("🚀 Starting comprehensive integration registration...")
    
    # Core Communication Integrations
    _register_communication_integrations(app)
    
    # Development & Project Management Integrations
    _register_development_integrations(app)
    
    # Business & Enterprise Integrations
    _register_business_integrations(app)
    
    # AI & Analytics Integrations
    _register_ai_integrations(app)
    
    # OAuth Handlers
    _register_oauth_handlers(app)
    
    logging.info(f"✅ Integration registration complete. Registered {len(integration_registry.integrations)} integrations.")

def _register_communication_integrations(app):
    """Register communication platform integrations"""
    
    # Slack Integration
    try:
        from integrations.slack_routes import slack_bp
        app.register_blueprint(slack_bp, url_prefix='/api/integrations/slack')
        integration_registry.register_integration('slack', {'status': 'registered', 'blueprint': slack_bp})
        logging.info("✅ Slack integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Slack integration not available: {e}")
    
    # Microsoft Teams Integration
    try:
        from integrations.teams_routes import teams_bp
        app.register_blueprint(teams_bp, url_prefix='/api/integrations/teams')
        integration_registry.register_integration('teams', {'status': 'registered', 'blueprint': teams_bp})
        logging.info("✅ Teams integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Teams integration not available: {e}")
    
    # Discord Integration
    try:
        from integrations.discord_routes import discord_bp
        app.register_blueprint(discord_bp, url_prefix='/api/integrations/discord')
        integration_registry.register_integration('discord', {'status': 'registered', 'blueprint': discord_bp})
        logging.info("✅ Discord integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Discord integration not available: {e}")

def _register_development_integrations(app):
    """Register development and project management integrations"""
    
    # GitHub Integration
    try:
        from integrations.github_routes import github_bp
        app.register_blueprint(github_bp, url_prefix='/api/integrations/github')
        integration_registry.register_integration('github', {'status': 'registered', 'blueprint': github_bp})
        logging.info("✅ GitHub integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  GitHub integration not available: {e}")
    
    # Linear Integration
    try:
        from integrations.linear_routes import linear_bp
        app.register_blueprint(linear_bp, url_prefix='/api/integrations/linear')
        integration_registry.register_integration('linear', {'status': 'registered', 'blueprint': linear_bp})
        logging.info("✅ Linear integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Linear integration not available: {e}")
    
    # Jira Integration
    try:
        from integrations.jira_routes import jira_bp
        app.register_blueprint(jira_bp, url_prefix='/api/integrations/jira')
        integration_registry.register_integration('jira', {'status': 'registered', 'blueprint': jira_bp})
        logging.info("✅ Jira integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Jira integration not available: {e}")
    
    # Asana Integration
    try:
        from integrations.asana_routes import asana_bp
        app.register_blueprint(asana_bp, url_prefix='/api/integrations/asana')
        integration_registry.register_integration('asana', {'status': 'registered', 'blueprint': asana_bp})
        logging.info("✅ Asana integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Asana integration not available: {e}")
    
    # Notion Integration
    try:
        from integrations.notion_routes import notion_bp
        app.register_blueprint(notion_bp, url_prefix='/api/integrations/notion')
        integration_registry.register_integration('notion', {'status': 'registered', 'blueprint': notion_bp})
        logging.info("✅ Notion integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Notion integration not available: {e}")
    
    # Trello Integration
    try:
        from integrations.trello_routes import trello_bp
        app.register_blueprint(trello_bp, url_prefix='/api/integrations/trello')
        integration_registry.register_integration('trello', {'status': 'registered', 'blueprint': trello_bp})
        logging.info("✅ Trello integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Trello integration not available: {e}")

def _register_business_integrations(app):
    """Register business and enterprise integrations"""
    
    # Salesforce Integration
    try:
        from integrations.salesforce_routes import salesforce_bp
        app.register_blueprint(salesforce_bp, url_prefix='/api/integrations/salesforce')
        integration_registry.register_integration('salesforce', {'status': 'registered', 'blueprint': salesforce_bp})
        logging.info("✅ Salesforce integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Salesforce integration not available: {e}")
    
    # HubSpot Integration
    try:
        from integrations.hubspot_routes import hubspot_bp
        app.register_blueprint(hubspot_bp, url_prefix='/api/integrations/hubspot')
        integration_registry.register_integration('hubspot', {'status': 'registered', 'blueprint': hubspot_bp})
        logging.info("✅ HubSpot integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  HubSpot integration not available: {e}")
    
    # Stripe Integration
    try:
        from integrations.stripe_routes import stripe_bp
        app.register_blueprint(stripe_bp, url_prefix='/api/integrations/stripe')
        integration_registry.register_integration('stripe', {'status': 'registered', 'blueprint': stripe_bp})
        logging.info("✅ Stripe integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Stripe integration not available: {e}")
    
    # Zoom Integration
    try:
        from integrations.zoom_routes import zoom_bp
        app.register_blueprint(zoom_bp, url_prefix='/api/integrations/zoom')
        integration_registry.register_integration('zoom', {'status': 'registered', 'blueprint': zoom_bp})
        logging.info("✅ Zoom integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Zoom integration not available: {e}")
    
    # Shopify Integration
    try:
        from integrations.shopify_routes import shopify_bp
        app.register_blueprint(shopify_bp, url_prefix='/api/integrations/shopify')
        integration_registry.register_integration('shopify', {'status': 'registered', 'blueprint': shopify_bp})
        logging.info("✅ Shopify integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Shopify integration not available: {e}")

def _register_ai_integrations(app):
    """Register AI and analytics integrations"""
    
    # AI Integration
    try:
        from integrations.ai_routes import ai_bp
        app.register_blueprint(ai_bp, url_prefix='/api/integrations/ai')
        integration_registry.register_integration('ai', {'status': 'registered', 'blueprint': ai_bp})
        logging.info("✅ AI integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  AI integration not available: {e}")
    
    # Enhanced AI Integration
    try:
        from integrations.ai_enhanced_api_routes import ai_enhanced_bp
        app.register_blueprint(ai_enhanced_bp, url_prefix='/api/integrations/ai-enhanced')
        integration_registry.register_integration('ai-enhanced', {'status': 'registered', 'blueprint': ai_enhanced_bp})
        logging.info("✅ Enhanced AI integration registered")
    except ImportError as e:
        logging.warning(f"⚠️  Enhanced AI integration not available: {e}")

def _register_oauth_handlers(app):
    """Register OAuth handlers"""
    
    # GitHub OAuth
    try:
        from auth_handler_github import auth_github_bp
        app.register_blueprint(auth_github_bp, url_prefix='/api/auth/github')
        integration_registry.register_oauth_handler('github', {'blueprint': auth_github_bp})
        logging.info("✅ GitHub OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  GitHub OAuth handler not available: {e}")
    
    # Linear OAuth
    try:
        from auth_handler_linear import auth_linear_bp
        app.register_blueprint(auth_linear_bp, url_prefix='/api/auth/linear')
        integration_registry.register_oauth_handler('linear', {'blueprint': auth_linear_bp})
        logging.info("✅ Linear OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Linear OAuth handler not available: {e}")
    
    # Jira OAuth
    try:
        from auth_handler_jira import auth_jira_bp
        app.register_blueprint(auth_jira_bp, url_prefix='/api/auth/jira')
        integration_registry.register_oauth_handler('jira', {'blueprint': auth_jira_bp})
        logging.info("✅ Jira OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Jira OAuth handler not available: {e}")
    
    # Asana OAuth
    try:
        from auth_handler_asana import auth_asana_bp
        app.register_blueprint(auth_asana_bp, url_prefix='/api/auth/asana')
        integration_registry.register_oauth_handler('asana', {'blueprint': auth_asana_bp})
        logging.info("✅ Asana OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Asana OAuth handler not available: {e}")
    
    # Notion OAuth
    try:
        from auth_handler_notion import auth_notion_bp
        app.register_blueprint(auth_notion_bp, url_prefix='/api/auth/notion')
        integration_registry.register_oauth_handler('notion', {'blueprint': auth_notion_bp})
        logging.info("✅ Notion OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Notion OAuth handler not available: {e}")
    
    # Slack OAuth
    try:
        from auth_handler_slack import auth_slack_bp
        app.register_blueprint(auth_slack_bp, url_prefix='/api/auth/slack')
        integration_registry.register_oauth_handler('slack', {'blueprint': auth_slack_bp})
        logging.info("✅ Slack OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Slack OAuth handler not available: {e}")
    
    # Teams OAuth
    try:
        from auth_handler_teams import auth_teams_bp
        app.register_blueprint(auth_teams_bp, url_prefix='/api/auth/teams')
        integration_registry.register_oauth_handler('teams', {'blueprint': auth_teams_bp})
        logging.info("✅ Teams OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Teams OAuth handler not available: {e}")
    
    # Trello OAuth
    try:
        from auth_handler_trello import auth_trello_bp
        app.register_blueprint(auth_trello_bp, url_prefix='/api/auth/trello')
        integration_registry.register_oauth_handler('trello', {'blueprint': auth_trello_bp})
        logging.info("✅ Trello OAuth handler registered")
    except ImportError as e:
        logging.warning(f"⚠️  Trello OAuth handler not available: {e}")

def get_integration_status():
    """Get the status of all registered integrations"""
    return {
        'integrations': integration_registry.integrations,
        'oauth_handlers': integration_registry.oauth_handlers,
        'services': integration_registry.services,
        'total_registered': len(integration_registry.integrations) + len(integration_registry.oauth_handlers) + len(integration_registry.services)
    }

def create_health_check_endpoints(app):
    """Create comprehensive health check endpoints for all integrations"""
    
    @app.route('/api/integrations/health', methods=['GET'])
    def integrations_health():
        """Health check for all integrations"""
        status = get_integration_status()
        return jsonify({
            'status': 'healthy',
            'integrations_registered': status['total_registered'],
            'integrations': list(status['integrations'].keys()),
            'oauth_handlers': list(status['oauth_handlers'].keys()),
            'timestamp': datetime.utcnow().isoformat()
        })
    
    @app.route('/api/integrations/status', methods=['GET'])
    def integrations_status():
        """Detailed status of all integrations"""
        return jsonify(get_integration_status())

# Export functions for use in main_api_app.py
__all__ = [
    'register_all_integrations',
    'get_integration_status', 
    'create_health_check_endpoints',
    'integration_registry'
]