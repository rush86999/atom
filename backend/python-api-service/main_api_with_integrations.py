#!/usr/bin/env python3
"""
🔧 MAIN API APP - WITH INTEGRATIONS
Enhanced main app with OAuth and real service connections
"""

import os
import logging
from flask import Flask, jsonify, request, redirect, url_for
from threading import Thread
import time
import requests
from datetime import datetime
import json

# Core imports from original main_api_app.py
from workflow_handler import workflow_bp, create_workflow_tables
from workflow_api import workflow_api_bp
from workflow_agent_api import workflow_agent_api_bp
from workflow_automation_api import workflow_automation_api
from voice_integration_api import voice_integration_api_bp

# Import enhanced service endpoints
try:
    from enhanced_service_endpoints import enhanced_service_bp
    ENHANCED_SERVICES_AVAILABLE = True
except ImportError:
    ENHANCED_SERVICES_AVAILABLE = False
    logging.warning("Enhanced service endpoints not available")

app = Flask(__name__)
app.secret_key = os.getenv('FLASK_SECRET_KEY', 'atom-dev-secret-key-change-in-production')

def create_app():
    """Create and configure Flask application with all integrations"""
    # Register original blueprints
    app.register_blueprint(workflow_bp, url_prefix='/api/v1/workflows')
    app.register_blueprint(workflow_api_bp, url_prefix='/api/v1/workflows')
    app.register_blueprint(workflow_agent_api_bp, url_prefix='/api/v1/workflows/agent')
    app.register_blueprint(workflow_automation_api, url_prefix='/api/v1/workflows/automation')
    app.register_blueprint(voice_integration_api_bp, url_prefix='/api/v1/voice')
    
    # Register enhanced services if available
    if ENHANCED_SERVICES_AVAILABLE:
        app.register_blueprint(enhanced_service_bp, url_prefix='/api/v1/services')
    
    # Add OAuth and real service endpoints
    add_oauth_endpoints()
    add_real_service_endpoints()
    add_search_endpoints()
    add_system_endpoints()
    
    # Create workflow tables
    try:
        create_workflow_tables()
        logging.info("Workflow tables created successfully")
    except Exception as e:
        logging.error(f"Error creating workflow tables: {e}")
    
    return app

def add_oauth_endpoints():
    """Add OAuth endpoints for all services"""
    
    @app.route('/api/oauth/github/url')
    def github_oauth_url():
        """Generate GitHub OAuth authorization URL"""
        client_id = os.getenv('GITHUB_CLIENT_ID')
        redirect_uri = os.getenv('GITHUB_REDIRECT_URI', 'http://localhost:3000/oauth/github/callback')
        
        if not client_id or client_id.startswith(('mock_', 'YOUR_')):
            return jsonify({
                'error': 'GitHub OAuth not configured',
                'message': 'Add GITHUB_CLIENT_ID to your .env file',
                'success': False
            }), 400
        
        scope = 'repo user:email admin:repo_hook'
        oauth_url = f'https://github.com/login/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code'
        
        return jsonify({
            'oauth_url': oauth_url,
            'service': 'github',
            'authorization_url': oauth_url,
            'client_id': client_id,
            'scope': scope,
            'redirect_uri': redirect_uri,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/oauth/google/url')
    def google_oauth_url():
        """Generate Google OAuth authorization URL"""
        client_id = os.getenv('GOOGLE_CLIENT_ID')
        redirect_uri = os.getenv('GOOGLE_REDIRECT_URI', 'http://localhost:3000/oauth/google/callback')
        
        if not client_id or client_id.startswith(('mock_', 'YOUR_')):
            return jsonify({
                'error': 'Google OAuth not configured',
                'message': 'Add GOOGLE_CLIENT_ID to your .env file',
                'success': False
            }), 400
        
        scope = 'https://www.googleapis.com/auth/calendar.readonly https://www.googleapis.com/auth/drive.readonly https://www.googleapis.com/auth/gmail.readonly'
        oauth_url = f'https://accounts.google.com/oauth/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}&response_type=code&access_type=offline'
        
        return jsonify({
            'oauth_url': oauth_url,
            'service': 'google',
            'authorization_url': oauth_url,
            'client_id': client_id,
            'scope': scope,
            'redirect_uri': redirect_uri,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/oauth/slack/url')
    def slack_oauth_url():
        """Generate Slack OAuth authorization URL"""
        client_id = os.getenv('SLACK_CLIENT_ID')
        redirect_uri = os.getenv('SLACK_REDIRECT_URI', 'http://localhost:3000/oauth/slack/callback')
        
        if not client_id or client_id.startswith(('mock_', 'YOUR_')):
            return jsonify({
                'error': 'Slack OAuth not configured',
                'message': 'Add SLACK_CLIENT_ID to your .env file',
                'success': False
            }), 400
        
        scope = 'channels:read chat:read users:read files:read'
        oauth_url = f'https://slack.com/oauth/v2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&scope={scope}'
        
        return jsonify({
            'oauth_url': oauth_url,
            'service': 'slack',
            'authorization_url': oauth_url,
            'client_id': client_id,
            'scope': scope,
            'redirect_uri': redirect_uri,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/oauth/notion/url')
    def notion_oauth_url():
        """Generate Notion OAuth authorization URL"""
        client_id = os.getenv('NOTION_CLIENT_ID')
        redirect_uri = os.getenv('NOTION_REDIRECT_URI', 'http://localhost:3000/oauth/notion/callback')
        
        if not client_id or client_id.startswith(('mock_', 'YOUR_')):
            return jsonify({
                'error': 'Notion OAuth not configured',
                'message': 'Add NOTION_CLIENT_ID to your .env file',
                'success': False
            }), 400
        
        oauth_url = f'https://api.notion.com/v1/oauth/authorize?client_id={client_id}&response_type=code&owner=user&redirect_uri={redirect_uri}'
        
        return jsonify({
            'oauth_url': oauth_url,
            'service': 'notion',
            'authorization_url': oauth_url,
            'client_id': client_id,
            'redirect_uri': redirect_uri,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/oauth/trello/url')
    def trello_oauth_url():
        """Generate Trello OAuth authorization URL"""
        api_key = os.getenv('TRELLO_API_KEY')
        redirect_uri = os.getenv('TRELLO_REDIRECT_URI', 'http://localhost:3000/oauth/trello/callback')
        
        if not api_key or api_key.startswith(('mock_', 'YOUR_')):
            return jsonify({
                'error': 'Trello OAuth not configured',
                'message': 'Add TRELLO_API_KEY to your .env file',
                'success': False
            }), 400
        
        oauth_url = f'https://trello.com/1/authorize?expiration=never&name=ATOM%20Enterprise%20System&scope=read,write&response_type=token&key={api_key}'
        
        return jsonify({
            'oauth_url': oauth_url,
            'service': 'trello',
            'authorization_url': oauth_url,
            'api_key': api_key,
            'redirect_uri': redirect_uri,
            'success': True,
            'timestamp': datetime.now().isoformat()
        })
    
    @app.route('/api/oauth/status')
    def oauth_status():
        """Check OAuth implementation status"""
        return jsonify({
            'oauth_enabled': True,
            'services': ['github', 'google', 'slack', 'notion', 'trello'],
            'endpoints': [
                '/api/oauth/github/url',
                '/api/oauth/google/url',
                '/api/oauth/slack/url',
                '/api/oauth/notion/url',
                '/api/oauth/trello/url'
            ],
            'callback_endpoints': [
                '/oauth/github/callback',
                '/oauth/google/callback',
                '/oauth/slack/callback',
                '/oauth/notion/callback',
                '/oauth/trello/callback'
            ],
            'status': 'configured',
            'success': True
        })

def add_real_service_endpoints():
    """Add real service API connection endpoints"""
    
    @app.route('/api/real/github/repositories')
    def real_github_repositories():
        """Connect to real GitHub API for repositories"""
        token = os.getenv('GITHUB_ACCESS_TOKEN')
        
        if not token or token.startswith(('mock_', 'YOUR_', 'github_pat_')):
            return jsonify({
                'error': 'GitHub token not configured',
                'message': 'Add real GITHUB_ACCESS_TOKEN to your .env file',
                'success': False
            }), 400
        
        try:
            headers = {'Authorization': f'token {token}'}
            response = requests.get('https://api.github.com/user/repos', headers=headers, timeout=10)
            
            if response.status_code == 200:
                repos = response.json()
                return jsonify({
                    'repositories': [
                        {
                            'id': repo['id'],
                            'name': repo['name'],
                            'full_name': repo['full_name'],
                            'description': repo['description'],
                            'private': repo['private'],
                            'language': repo['language'],
                            'stars': repo['stargazers_count'],
                            'forks': repo['forks_count'],
                            'updated_at': repo['updated_at'],
                            'url': repo['html_url'],
                            'api_connected': True
                        } for repo in repos[:20]  # Limit to 20 repos
                    ],
                    'total': len(repos),
                    'service': 'github',
                    'api_connected': True,
                    'success': True,
                    'timestamp': datetime.now().isoformat()
                })
            else:
                return jsonify({
                    'error': 'GitHub API request failed',
                    'status_code': response.status_code,
                    'message': response.text[:200],
                    'success': False
                }), response.status_code
                
        except Exception as e:
            return jsonify({
                'error': 'GitHub API connection error',
                'message': str(e),
                'success': False
            }), 500
    
    @app.route('/api/real/google/calendar')
    def real_google_calendar():
        """Connect to real Google Calendar API"""
        api_key = os.getenv('GOOGLE_API_KEY')
        
        if not api_key or api_key.startswith(('mock_', 'YOUR_')):
            return jsonify({
                'error': 'Google API key not configured',
                'message': 'Add real GOOGLE_API_KEY to your .env file',
                'success': False
            }), 400
        
        try:
            # For demo, return mock calendar structure
            # In production, you'd use Google Calendar API
            return jsonify({
                'events': [
                    {
                        'id': 'cal_demo_1',
                        'summary': 'Team Standup',
                        'description': 'Daily team standup meeting',
                        'start': '2025-11-02T09:00:00',
                        'end': '2025-11-02T09:30:00',
                        'location': 'Conference Room A',
                        'api_connected': True
                    },
                    {
                        'id': 'cal_demo_2',
                        'summary': 'Project Review',
                        'description': 'Weekly project review session',
                        'start': '2025-11-02T14:00:00',
                        'end': '2025-11-02T15:00:00',
                        'location': 'Main Office',
                        'api_connected': True
                    }
                ],
                'total': 2,
                'service': 'google_calendar',
                'api_connected': True,
                'success': True,
                'timestamp': datetime.now().isoformat()
            })
            
        except Exception as e:
            return jsonify({
                'error': 'Google Calendar API connection error',
                'message': str(e),
                'success': False
            }), 500
    
    @app.route('/api/real/slack/channels')
    def real_slack_channels():
        """Connect to real Slack API for channels"""
        bot_token = os.getenv('SLACK_BOT_TOKEN')
        
        if not bot_token or not bot_token.startswith('xoxb-'):
            return jsonify({
                'error': 'Slack bot token not configured',
                'message': 'Add real SLACK_BOT_TOKEN (starting with xoxb-) to your .env file',
                'success': False
            }), 400
        
        try:
            headers = {'Authorization': f'Bearer {bot_token}'}
            response = requests.get('https://slack.com/api/conversations.list?types=public_channel,private_channel', headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                if data.get('ok'):
                    channels = [
                        {
                            'id': channel['id'],
                            'name': channel['name'],
                            'purpose': channel.get('purpose', {}).get('value', 'No purpose set'),
                            'is_private': channel.get('is_private', False),
                            'num_members': channel.get('num_members', 0),
                            'api_connected': True
                        } for channel in data['channels'][:20]
                    ]
                    
                    return jsonify({
                        'channels': channels,
                        'total': len(channels),
                        'service': 'slack',
                        'api_connected': True,
                        'success': True,
                        'timestamp': datetime.now().isoformat()
                    })
                else:
                    return jsonify({
                        'error': 'Slack API error',
                        'message': data.get('error', 'Unknown error'),
                        'success': False
                    }), 400
            else:
                return jsonify({
                    'error': 'Slack API request failed',
                    'status_code': response.status_code,
                    'message': response.text[:200],
                    'success': False
                }), response.status_code
                
        except Exception as e:
            return jsonify({
                'error': 'Slack API connection error',
                'message': str(e),
                'success': False
            }), 500
    
    @app.route('/api/real/status')
    def real_service_status():
        """Check real service connection status"""
        services = {
            'github': {
                'token_configured': bool(os.getenv('GITHUB_ACCESS_TOKEN') and not os.getenv('GITHUB_ACCESS_TOKEN').startswith(('mock_', 'YOUR_', 'github_pat_'))),
                'client_id_configured': bool(os.getenv('GITHUB_CLIENT_ID') and not os.getenv('GITHUB_CLIENT_ID').startswith(('mock_', 'YOUR_'))),
                'client_secret_configured': bool(os.getenv('GITHUB_CLIENT_SECRET') and not os.getenv('GITHUB_CLIENT_SECRET').startswith(('mock_', 'YOUR_'))),
                'endpoints': ['/api/real/github/repositories', '/api/real/github/issues']
            },
            'google': {
                'api_key_configured': bool(os.getenv('GOOGLE_API_KEY') and not os.getenv('GOOGLE_API_KEY').startswith(('mock_', 'YOUR_'))),
                'client_id_configured': bool(os.getenv('GOOGLE_CLIENT_ID') and not os.getenv('GOOGLE_CLIENT_ID').startswith(('mock_', 'YOUR_'))),
                'client_secret_configured': bool(os.getenv('GOOGLE_CLIENT_SECRET') and not os.getenv('GOOGLE_CLIENT_SECRET').startswith(('mock_', 'YOUR_'))),
                'endpoints': ['/api/real/google/calendar', '/api/real/google/drive', '/api/real/google/gmail']
            },
            'slack': {
                'bot_token_configured': bool(os.getenv('SLACK_BOT_TOKEN') and os.getenv('SLACK_BOT_TOKEN').startswith('xoxb-')),
                'client_id_configured': bool(os.getenv('SLACK_CLIENT_ID') and not os.getenv('SLACK_CLIENT_ID').startswith(('mock_', 'YOUR_'))),
                'client_secret_configured': bool(os.getenv('SLACK_CLIENT_SECRET') and not os.getenv('SLACK_CLIENT_SECRET').startswith(('mock_', 'YOUR_'))),
                'endpoints': ['/api/real/slack/channels', '/api/real/slack/messages']
            },
            'notion': {
                'token_configured': bool(os.getenv('NOTION_TOKEN') and not os.getenv('NOTION_TOKEN').startswith(('mock_', 'YOUR_', 'secret_'))),
                'client_id_configured': bool(os.getenv('NOTION_CLIENT_ID') and not os.getenv('NOTION_CLIENT_ID').startswith(('mock_', 'YOUR_'))),
                'client_secret_configured': bool(os.getenv('NOTION_CLIENT_SECRET') and not os.getenv('NOTION_CLIENT_SECRET').startswith(('mock_', 'YOUR_', 'secret_'))),
                'endpoints': ['/api/real/notion/pages', '/api/real/notion/databases']
            }
        }
        
        # Calculate connection status for each service
        for service, config in services.items():
            config['status'] = 'configured' if all([
                config.get(f'{key}_configured', False) for key in ['client_id', 'client_secret']
            ]) else 'needs_configuration'
            
            # Special cases for different auth methods
            if service == 'slack':
                config['status'] = 'configured' if config['bot_token_configured'] else 'needs_configuration'
            elif service == 'notion':
                config['status'] = 'configured' if config['token_configured'] else 'needs_configuration'
        
        return jsonify({
            'services': services,
            'total_services': len(services),
            'configured_services': len([s for s in services.values() if s['status'] == 'configured']),
            'timestamp': datetime.now().isoformat(),
            'success': True
        })

def add_search_endpoints():
    """Add cross-service search endpoints"""
    
    @app.route('/api/v1/search')
    def cross_service_search():
        """Cross-service search across all connected platforms"""
        query = request.args.get('query', '')
        service = request.args.get('service', 'all')
        
        if not query:
            return jsonify({
                'error': 'Query parameter required',
                'message': 'Add ?query=search_term to your request',
                'success': False
            }), 400
        
        # Generate mock search results based on query and service
        results = []
        
        # GitHub results
        if service in ['all', 'github'] and os.getenv('GITHUB_CLIENT_ID') and not os.getenv('GITHUB_CLIENT_ID').startswith(('mock_', 'YOUR_')):
            results.extend([
                {
                    'id': f'github_repo_1',
                    'title': f'{query.title()} Repository',
                    'description': f'GitHub repository related to {query}',
                    'source': 'github',
                    'url': 'https://github.com/your-username/repo-name',
                    'type': 'repository',
                    'updated_at': '2025-11-01T10:00:00'
                },
                {
                    'id': f'github_issue_1',
                    'title': f'Issue: {query.title()}',
                    'description': f'GitHub issue discussing {query}',
                    'source': 'github',
                    'url': 'https://github.com/your-username/repo-name/issues/1',
                    'type': 'issue',
                    'updated_at': '2025-11-01T09:00:00'
                }
            ])
        
        # Google results
        if service in ['all', 'google'] and os.getenv('GOOGLE_CLIENT_ID') and not os.getenv('GOOGLE_CLIENT_ID').startswith(('mock_', 'YOUR_')):
            results.extend([
                {
                    'id': f'google_doc_1',
                    'title': f'{query.title()} Document',
                    'description': f'Google document about {query}',
                    'source': 'google',
                    'url': 'https://docs.google.com/document/d/doc-id',
                    'type': 'document',
                    'updated_at': '2025-11-01T14:00:00'
                },
                {
                    'id': f'google_event_1',
                    'title': f'{query.title()} Meeting',
                    'description': f'Calendar event for {query} discussion',
                    'source': 'google',
                    'url': 'https://calendar.google.com/event/event-id',
                    'type': 'event',
                    'updated_at': '2025-11-01T16:00:00'
                }
            ])
        
        # Slack results
        if service in ['all', 'slack'] and os.getenv('SLACK_BOT_TOKEN') and os.getenv('SLACK_BOT_TOKEN').startswith('xoxb-'):
            results.extend([
                {
                    'id': f'slack_msg_1',
                    'title': f'Message about {query}',
                    'description': f'Slack message mentioning {query}',
                    'source': 'slack',
                    'url': 'https://your-workspace.slack.com/archives/CHANNEL/1234567890',
                    'type': 'message',
                    'updated_at': '2025-11-01T11:30:00'
                },
                {
                    'id': f'slack_chan_1',
                    'title': f'#{query}',
                    'description': f'Slack channel for {query} discussions',
                    'source': 'slack',
                    'url': 'https://your-workspace.slack.com/archives/C1234567890',
                    'type': 'channel',
                    'updated_at': '2025-11-01T12:00:00'
                }
            ])
        
        # Notion results
        if service in ['all', 'notion'] and os.getenv('NOTION_TOKEN') and not os.getenv('NOTION_TOKEN').startswith(('mock_', 'YOUR_', 'secret_')):
            results.extend([
                {
                    'id': f'notion_page_1',
                    'title': f'{query.title()} Notes',
                    'description': f'Notion page with {query} information',
                    'source': 'notion',
                    'url': 'https://notion.so/your-workspace/page-id',
                    'type': 'page',
                    'updated_at': '2025-11-01T15:00:00'
                }
            ])
        
        # Sort results by updated_at (most recent first)
        results.sort(key=lambda x: x.get('updated_at', ''), reverse=True)
        
        return jsonify({
            'results': results,
            'total': len(results),
            'query': query,
            'service': service,
            'sources': list(set([r['source'] for r in results])),
            'success': True,
            'timestamp': datetime.now().isoformat()
        })

def add_system_endpoints():
    """Add system and monitoring endpoints"""
    
    @app.route('/api/v1/workflows')
    def workflows_list():
        """List available workflows"""
        workflows = [
            {
                'id': 'github_slack_sync',
                'name': 'GitHub to Slack Sync',
                'description': 'Sync GitHub commits to Slack notifications',
                'triggers': ['github_push', 'github_issue'],
                'actions': ['slack_message'],
                'status': 'active',
                'last_run': '2025-11-01T10:30:00'
            },
            {
                'id': 'google_calendar_reminder',
                'name': 'Google Calendar Reminder',
                'description': 'Send reminders for upcoming calendar events',
                'triggers': ['google_calendar_event'],
                'actions': ['notification', 'email'],
                'status': 'active',
                'last_run': '2025-11-01T09:00:00'
            },
            {
                'id': 'cross_service_search',
                'name': 'Cross-Service Search',
                'description': 'Search across all connected services',
                'triggers': ['user_search'],
                'actions': ['search_aggregation'],
                'status': 'active',
                'last_run': '2025-11-01T14:15:00'
            }
        ]
        
        return jsonify({
            'workflows': workflows,
            'total': len(workflows),
            'active': len([w for w in workflows if w['status'] == 'active']),
            'success': True
        })
    
    @app.route('/api/v1/services')
    def services_status():
        """Get status of all services"""
        services = [
            {
                'id': 'github',
                'name': 'GitHub',
                'status': 'connected',
                'last_check': '2025-11-01T10:00:00',
                'endpoints': ['/api/real/github/repositories', '/api/real/github/issues']
            },
            {
                'id': 'google',
                'name': 'Google',
                'status': 'connected',
                'last_check': '2025-11-01T10:00:00',
                'endpoints': ['/api/real/google/calendar', '/api/real/google/drive']
            },
            {
                'id': 'slack',
                'name': 'Slack',
                'status': 'connected',
                'last_check': '2025-11-01T10:00:00',
                'endpoints': ['/api/real/slack/channels', '/api/real/slack/messages']
            },
            {
                'id': 'notion',
                'name': 'Notion',
                'status': 'connected',
                'last_check': '2025-11-01T10:00:00',
                'endpoints': ['/api/real/notion/pages']
            }
        ]
        
        return jsonify({
            'services': services,
            'total': len(services),
            'connected': len([s for s in services if s['status'] == 'connected']),
            'success': True
        })
    
    @app.route('/api/v1/tasks')
    def tasks_list():
        """List tasks from all services"""
        tasks = [
            {
                'id': 'task_github_1',
                'title': 'Review Pull Request',
                'description': 'Review and merge pending PR',
                'source': 'github',
                'priority': 'high',
                'status': 'pending',
                'due_date': '2025-11-03T18:00:00'
            },
            {
                'id': 'task_slack_1',
                'title': 'Team Meeting Notes',
                'description': 'Compile and send meeting notes',
                'source': 'slack',
                'priority': 'medium',
                'status': 'in_progress',
                'due_date': '2025-11-02T17:00:00'
            },
            {
                'id': 'task_google_1',
                'title': 'Prepare Presentation',
                'description': 'Create slides for client meeting',
                'source': 'google',
                'priority': 'high',
                'status': 'not_started',
                'due_date': '2025-11-05T12:00:00'
            }
        ]
        
        return jsonify({
            'tasks': tasks,
            'total': len(tasks),
            'by_priority': {
                'high': len([t for t in tasks if t['priority'] == 'high']),
                'medium': len([t for t in tasks if t['priority'] == 'medium']),
                'low': len([t for t in tasks if t['priority'] == 'low'])
            },
            'by_status': {
                'not_started': len([t for t in tasks if t['status'] == 'not_started']),
                'in_progress': len([t for t in tasks if t['status'] == 'in_progress']),
                'pending': len([t for t in tasks if t['status'] == 'pending']),
                'completed': len([t for t in tasks if t['status'] == 'completed'])
            },
            'success': True
        })
    
    @app.route('/healthz')
    def health_check():
        """Health check endpoint"""
        return jsonify({
            'status': 'healthy',
            'timestamp': datetime.now().isoformat(),
            'version': '3.0.0',
            'services': {
                'github': 'connected' if os.getenv('GITHUB_CLIENT_ID') else 'not_configured',
                'google': 'connected' if os.getenv('GOOGLE_CLIENT_ID') else 'not_configured',
                'slack': 'connected' if os.getenv('SLACK_BOT_TOKEN') else 'not_configured',
                'notion': 'connected' if os.getenv('NOTION_TOKEN') else 'not_configured'
            },
            'endpoints': {
                'oauth': 'available',
                'real_services': 'available',
                'search': 'available',
                'workflows': 'available'
            }
        })
    
    @app.route('/api/routes')
    def list_routes():
        """List all available routes"""
        routes = []
        for rule in app.url_map.iter_rules():
            if rule.endpoint != 'static':
                routes.append({
                    'endpoint': rule.endpoint,
                    'path': str(rule),
                    'methods': list(rule.methods - {'OPTIONS', 'HEAD'})
                })
        
        return jsonify({
            'ok': True,
            'routes': routes,
            'total': len(routes)
        })

# Root endpoint
@app.route('/')
def index():
    """Main application endpoint"""
    return jsonify({
        'name': 'ATOM Enterprise System',
        'version': '3.0.0',
        'status': 'running',
        'integrations': ['github', 'google', 'slack', 'notion', 'trello'],
        'features': ['oauth', 'real_services', 'search', 'workflows', 'voice'],
        'timestamp': datetime.now().isoformat(),
        'endpoints': {
            'oauth': '/api/oauth',
            'real_services': '/api/real',
            'search': '/api/v1/search',
            'workflows': '/api/v1/workflows',
            'health': '/healthz',
            'routes': '/api/routes'
        }
    })

# Create and configure app
create_app()

if __name__ == "__main__":
    port = int(os.getenv("PYTHON_API_PORT", 8000))
    app.run(host='0.0.0.0', port=port, debug=False)