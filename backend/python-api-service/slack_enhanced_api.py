"""
ATOM Enhanced Slack API Handler
Complete Slack integration with comprehensive API operations
"""

import os
import logging
import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import Slack service
try:
    from slack_service_real import slack_service
    SLACK_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Slack service not available: {e}")
    SLACK_SERVICE_AVAILABLE = False
    slack_service = None

# Import database handler
try:
    from db_oauth_slack import get_user_slack_tokens, save_user_slack_tokens
    SLACK_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Slack database handler not available: {e}")
    SLACK_DB_AVAILABLE = False

slack_enhanced_bp = Blueprint("slack_enhanced_bp", __name__)

# Configuration
SLACK_API_BASE_URL = "https://slack.com/api"
REQUEST_TIMEOUT = 30
RATE_LIMIT_HEADERS = ['x-ratelimit-limit', 'x-ratelimit-remaining', 'x-ratelimit-reset']

async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Slack tokens for user"""
    if not SLACK_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            'access_token': os.getenv('SLACK_ACCESS_TOKEN'),
            'token_type': 'Bearer',
            'scope': 'channels:read,channels:history,groups:read,groups:history,im:read,im:history,mpim:read,mpim:history,users:read,files:read,reactions:read,team:read',
            'team_id': os.getenv('SLACK_TEAM_ID'),
            'team_name': os.getenv('SLACK_TEAM_NAME'),
            'user_id': user_id,
            'user_name': 'Test User',
            'bot_user_id': os.getenv('SLACK_BOT_USER_ID'),
            'expires_at': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
    
    try:
        tokens = await get_user_slack_tokens(user_id)
        return tokens
    except Exception as e:
        logger.error(f"Error getting Slack tokens for user {user_id}: {e}")
        return None

def format_slack_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format Slack API response"""
    return {
        'ok': True,
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'slack_web_api'
    }

def format_error_response(error: Exception, endpoint: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        'ok': False,
        'error': {
            'code': type(error).__name__,
            'message': str(error),
            'endpoint': endpoint
        },
        'timestamp': datetime.utcnow().isoformat(),
        'source': 'slack_web_api'
    }

@slack_enhanced_bp.route('/api/integrations/slack/workspaces', methods=['POST'])
async def list_workspaces():
    """List user Slack workspaces"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 50)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Slack tokens not found'}
            }), 401
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            workspaces = await slack_service.get_user_workspaces(user_id)
            
            workspaces_data = [{
                'id': ws.id,
                'name': ws.name,
                'domain': ws.domain,
                'url': ws.url,
                'icon': ws.icon,
                'enterprise_id': ws.enterprise_id,
                'enterprise_name': ws.enterprise_name
            } for ws in workspaces]
            
            return jsonify(format_slack_response({
                'workspaces': workspaces_data,
                'total_count': len(workspaces_data)
            }, 'list_workspaces'))
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SLACK_API_BASE_URL}/team.info",
                params={'team': tokens['team_id']},
                headers={'Authorization': f'Bearer {tokens["access_token"]}'}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('ok'):
                    team_data = result.get('team', {})
                    
                    workspace = {
                        'id': team_data.get('id'),
                        'name': team_data.get('name'),
                        'domain': team_data.get('domain'),
                        'url': team_data.get('url'),
                        'icon': team_data.get('icon'),
                        'enterprise_id': team_data.get('enterprise_id'),
                        'enterprise_name': team_data.get('enterprise_name')
                    }
                    
                    return jsonify(format_slack_response({
                        'workspaces': [workspace],
                        'total_count': 1
                    }, 'list_workspaces'))
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': result.get('error', 'Unknown error')}
                    })
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'HTTP {response.status_code}'}
                })
    
    except Exception as e:
        logger.error(f"Error listing workspaces: {e}")
        return jsonify(format_error_response(e, 'list_workspaces')), 500

@slack_enhanced_bp.route('/api/integrations/slack/channels', methods=['POST'])
async def list_channels():
    """List channels from workspace"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        include_private = data.get('include_private', False)
        include_archived = data.get('include_archived', False)
        limit = data.get('limit', 200)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Slack tokens not found'}
            }), 401
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            channels = await slack_service.get_workspace_channels(
                user_id, workspace_id or tokens['team_id'], 
                include_private, include_archived, limit
            )
            
            channels_data = [{
                'id': ch.id,
                'name': ch.name,
                'display_name': ch.display_name,
                'purpose': ch.purpose,
                'topic': ch.topic,
                'is_private': ch.is_private,
                'is_archived': ch.is_archived,
                'is_general': ch.is_general,
                'is_shared': ch.is_shared,
                'is_org_shared': ch.is_org_shared,
                'num_members': ch.num_members,
                'creator': ch.creator,
                'created': ch.created,
                'workspace_id': ch.workspace_id,
                'type': ch.type,
                'unread_count': ch.unread_count,
                'latest': ch.latest
            } for ch in channels]
            
            return jsonify(format_slack_response({
                'channels': channels_data,
                'total_count': len(channels_data)
            }, 'list_channels'))
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            all_channels = []
            cursor = None
            
            while True:
                response = await client.get(
                    f"{SLACK_API_BASE_URL}/conversations.list",
                    params={
                        'types': 'public_channel,private_channel,mpim,im',
                        'exclude_archived': not include_archived,
                        'limit': min(limit - len(all_channels), 100),
                        'cursor': cursor
                    },
                    headers={'Authorization': f'Bearer {tokens["access_token"]}'}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get('ok'):
                        channels_data = result.get('channels', [])
                        
                        for channel_data in channels_data:
                            # Filter private channels if not requested
                            if channel_data.get('is_private') and not include_private:
                                continue
                            
                            channel = {
                                'id': channel_data.get('id'),
                                'name': channel_data.get('name'),
                                'display_name': channel_data.get('name_normalized', channel_data.get('name')),
                                'purpose': channel_data.get('purpose', {}).get('value') if channel_data.get('purpose') else None,
                                'topic': channel_data.get('topic', {}).get('value') if channel_data.get('topic') else None,
                                'is_private': channel_data.get('is_private', False),
                                'is_archived': channel_data.get('is_archived', False),
                                'is_general': channel_data.get('is_general', False),
                                'is_shared': channel_data.get('is_shared', False),
                                'is_org_shared': channel_data.get('is_org_shared', False),
                                'num_members': channel_data.get('num_members', 0),
                                'creator': channel_data.get('creator'),
                                'created': channel_data.get('created', 0),
                                'workspace_id': workspace_id or tokens['team_id'],
                                'type': channel_data.get('is_im') and 'im' or 
                                       channel_data.get('is_mpim') and 'mpim' or 
                                       'channel'
                            }
                            
                            all_channels.append(channel)
                        
                        # Check if we have more results
                        if result.get('response_metadata', {}).get('next_cursor'):
                            cursor = result['response_metadata']['next_cursor']
                        else:
                            break
                    else:
                        return jsonify({
                            'ok': False,
                            'error': {'message': result.get('error', 'Unknown error')}
                        })
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': f'HTTP {response.status_code}'}
                    })
                
                if len(all_channels) >= limit:
                    break
            
            return jsonify(format_slack_response({
                'channels': all_channels[:limit],
                'total_count': len(all_channels[:limit])
            }, 'list_channels'))
    
    except Exception as e:
        logger.error(f"Error listing channels: {e}")
        return jsonify(format_error_response(e, 'list_channels')), 500

@slack_enhanced_bp.route('/api/integrations/slack/users', methods=['POST'])
async def list_users():
    """List users from workspace"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        include_restricted = data.get('include_restricted', False)
        include_bots = data.get('include_bots', False)
        limit = data.get('limit', 100)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Slack tokens not found'}
            }), 401
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            users = await slack_service.get_workspace_users(
                user_id, workspace_id or tokens['team_id'],
                include_restricted, include_bots, limit
            )
            
            users_data = [{
                'id': u.id,
                'name': u.name,
                'real_name': u.real_name,
                'display_name': u.display_name,
                'email': u.email,
                'team_id': u.team_id,
                'is_admin': u.is_admin,
                'is_owner': u.is_owner,
                'is_primary_owner': u.is_primary_owner,
                'is_restricted': u.is_restricted,
                'is_ultra_restricted': u.is_ultra_restricted,
                'is_bot': u.is_bot,
                'profile': u.profile
            } for u in users]
            
            return jsonify(format_slack_response({
                'users': users_data,
                'total_count': len(users_data)
            }, 'list_users'))
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            all_users = []
            cursor = None
            
            while True:
                response = await client.get(
                    f"{SLACK_API_BASE_URL}/users.list",
                    params={
                        'limit': min(limit - len(all_users), 100),
                        'cursor': cursor
                    },
                    headers={'Authorization': f'Bearer {tokens["access_token"]}'}
                )
                
                if response.status_code == 200:
                    result = response.json()
                    
                    if result.get('ok'):
                        users_data = result.get('members', [])
                        
                        for user_data in users_data:
                            # Filter based on preferences
                            if user_data.get('is_restricted') and not include_restricted:
                                continue
                            
                            if user_data.get('is_bot') and not include_bots and user_data.get('id') != tokens.get('bot_user_id'):
                                continue
                            
                            user = {
                                'id': user_data.get('id'),
                                'name': user_data.get('name'),
                                'real_name': user_data.get('real_name'),
                                'display_name': user_data.get('profile', {}).get('display_name') or user_data.get('name'),
                                'email': user_data.get('profile', {}).get('email'),
                                'team_id': workspace_id or tokens['team_id'],
                                'is_admin': user_data.get('is_admin', False),
                                'is_owner': user_data.get('is_owner', False),
                                'is_primary_owner': user_data.get('is_primary_owner', False),
                                'is_restricted': user_data.get('is_restricted', False),
                                'is_ultra_restricted': user_data.get('is_ultra_restricted', False),
                                'is_bot': user_data.get('is_bot', False),
                                'profile': user_data.get('profile')
                            }
                            
                            all_users.append(user)
                        
                        # Check if we have more results
                        if result.get('response_metadata', {}).get('next_cursor'):
                            cursor = result['response_metadata']['next_cursor']
                        else:
                            break
                    else:
                        return jsonify({
                            'ok': False,
                            'error': {'message': result.get('error', 'Unknown error')}
                        })
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': f'HTTP {response.status_code}'}
                    })
                
                if len(all_users) >= limit:
                    break
            
            return jsonify(format_slack_response({
                'users': all_users[:limit],
                'total_count': len(all_users[:limit])
            }, 'list_users'))
    
    except Exception as e:
        logger.error(f"Error listing users: {e}")
        return jsonify(format_error_response(e, 'list_users')), 500

@slack_enhanced_bp.route('/api/integrations/slack/user/profile', methods=['POST'])
async def get_user_profile():
    """Get authenticated user profile"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Slack tokens not found'}
            }), 401
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            user = await slack_service.get_user_profile(user_id)
            
            if user:
                user_data = {
                    'id': user.id,
                    'name': user.name,
                    'real_name': user.real_name,
                    'display_name': user.display_name,
                    'email': user.email,
                    'team_id': user.team_id,
                    'is_admin': user.is_admin,
                    'is_owner': user.is_owner,
                    'is_primary_owner': user.is_primary_owner,
                    'is_restricted': user.is_restricted,
                    'is_ultra_restricted': user.is_ultra_restricted,
                    'is_bot': user.is_bot,
                    'profile': user.profile
                }
                
                return jsonify(format_slack_response(user_data, 'get_user_profile'))
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': 'User profile not found'}
                })
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SLACK_API_BASE_URL}/auth.test",
                headers={'Authorization': f'Bearer {tokens["access_token"]}'}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('ok'):
                    user_data = {
                        'id': result.get('user_id'),
                        'name': result.get('user'),
                        'real_name': result.get('user'),
                        'display_name': result.get('user'),
                        'team_id': result.get('team_id'),
                        'is_admin': result.get('is_admin', False),
                        'is_owner': False,
                        'is_primary_owner': False,
                        'is_restricted': False,
                        'is_ultra_restricted': False,
                        'is_bot': result.get('bot_id') is not None,
                        'profile': {}
                    }
                    
                    return jsonify(format_slack_response(user_data, 'get_user_profile'))
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': result.get('error', 'Unknown error')}
                    })
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'HTTP {response.status_code}'}
                })
    
    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, 'get_user_profile')), 500

@slack_enhanced_bp.route('/api/integrations/slack/messages', methods=['POST'])
async def list_messages():
    """List messages from channel"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        filters = data.get('filters', {})
        operation = data.get('operation', 'list')
        limit = data.get('limit', 100)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Slack tokens not found'}
            }), 401
        
        if operation == 'create':
            # Send message
            return await _send_message(user_id, tokens, data)
        
        # List messages
        if not channel_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'channel_id is required for listing messages'}
            }), 400
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            messages = await slack_service.get_channel_messages(
                user_id, channel_id, filters, limit
            )
            
            messages_data = [{
                'type': m.type,
                'subtype': m.subtype,
                'channel': m.channel,
                'user': m.user,
                'text': m.text,
                'ts': m.ts,
                'thread_ts': m.thread_ts,
                'reply_count': m.reply_count,
                'file': m.file,
                'files': m.files,
                'reactions': m.reactions,
                'starred': m.starred,
                'pinned': m.pinned,
                'is_starred': m.is_starred,
                'is_pinned': m.is_pinned
            } for m in messages]
            
            return jsonify(format_slack_response({
                'messages': messages_data,
                'total_count': len(messages_data)
            }, 'list_messages'))
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SLACK_API_BASE_URL}/conversations.history",
                params={
                    'channel': channel_id,
                    'limit': limit,
                    'oldest': filters.get('start_time'),
                    'latest': filters.get('end_time')
                },
                headers={'Authorization': f'Bearer {tokens["access_token"]}'}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('ok'):
                    messages_data = result.get('messages', [])
                    
                    # Apply filters
                    filtered_messages = []
                    for message_data in messages_data:
                        # Skip system messages
                        if message_data.get('messageType') == 'systemEventMessage':
                            continue
                        
                        # Apply filters
                        if filters.get('from') == 'me' and message_data.get('user') != user_id:
                            continue
                        
                        message = {
                            'type': message_data.get('type', 'message'),
                            'subtype': message_data.get('subtype'),
                            'channel': channel_id,
                            'user': message_data.get('user'),
                            'text': message_data.get('text'),
                            'ts': message_data.get('ts'),
                            'thread_ts': message_data.get('thread_ts'),
                            'reply_count': len(message_data.get('replies', [])) if message_data.get('replies') else None,
                            'file': message_data.get('file'),
                            'files': message_data.get('files'),
                            'reactions': message_data.get('reactions'),
                            'starred': message_data.get('is_starred', False),
                            'pinned': message_data.get('pinned_to', []) and message_data['pinned_to'][0] is not None,
                            'is_starred': message_data.get('is_starred', False),
                            'is_pinned': message_data.get('pinned_to', []) and message_data['pinned_to'][0] is not None
                        }
                        
                        filtered_messages.append(message)
                    
                    return jsonify(format_slack_response({
                        'messages': filtered_messages,
                        'total_count': len(filtered_messages)
                    }, 'list_messages'))
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': result.get('error', 'Unknown error')}
                    })
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'HTTP {response.status_code}'}
                })
    
    except Exception as e:
        logger.error(f"Error listing messages: {e}")
        return jsonify(format_error_response(e, 'list_messages')), 500

async def _send_message(user_id: str, tokens: Dict[str, Any], data: Dict[str, Any]) -> Dict[str, Any]:
    """Helper function to send message"""
    try:
        message_data = data.get('data', {})
        
        if not message_data.get('text'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Message text is required'}
            }), 400
        
        if not message_data.get('channelId'):
            return jsonify({
                'ok': False,
                'error': {'message': 'Channel ID is required'}
            }), 400
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            result = await slack_service.send_message(
                user_id, message_data['channelId'], 
                message_data['text'], message_data.get('threadTs')
            )
            
            if result.get('ok'):
                return jsonify(format_slack_response(result, 'send_message'))
            else:
                return jsonify(result)
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            payload = {
                'channel': message_data['channelId'],
                'text': message_data['text']
            }
            
            if message_data.get('threadTs'):
                payload['thread_ts'] = message_data['threadTs']
            
            response = await client.post(
                f"{SLACK_API_BASE_URL}/chat.postMessage",
                json=payload,
                headers={'Authorization': f'Bearer {tokens["access_token"]}'}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('ok'):
                    return jsonify(format_slack_response({
                        'message': result.get('message'),
                        'ts': result.get('ts'),
                        'channel': result.get('channel'),
                        'message': 'Message sent successfully'
                    }, 'send_message'))
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': result.get('error', 'Unknown error')}
                    })
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'HTTP {response.status_code}'}
                })
    
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        return jsonify(format_error_response(e, 'send_message')), 500

@slack_enhanced_bp.route('/api/integrations/slack/search', methods=['POST'])
async def search_slack():
    """Search across Slack"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query')
        search_type = data.get('type', 'messages')
        limit = data.get('limit', 50)
        
        if not user_id:
            return jsonify({
                'ok': False,
                'error': {'message': 'user_id is required'}
            }), 400
        
        if not query:
            return jsonify({
                'ok': False,
                'error': {'message': 'query is required'}
            }), 400
        
        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify({
                'ok': False,
                'error': {'message': 'Slack tokens not found'}
            }), 401
        
        # Use Slack service
        if SLACK_SERVICE_AVAILABLE:
            result = await slack_service.search_slack(user_id, query, search_type, limit)
            return jsonify(result)
        
        # Fallback to direct API
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{SLACK_API_BASE_URL}/search.messages",
                params={
                    'query': query,
                    'count': min(limit, 100)
                },
                headers={'Authorization': f'Bearer {tokens["access_token"]}'}
            )
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get('ok'):
                    return jsonify(format_slack_response({
                        'messages': result.get('messages', {}).get('matches', []),
                        'total_count': result.get('messages', {}).get('total', 0),
                        'query': query
                    }, 'search_slack'))
                else:
                    return jsonify({
                        'ok': False,
                        'error': {'message': result.get('error', 'Unknown error')}
                    })
            else:
                return jsonify({
                    'ok': False,
                    'error': {'message': f'HTTP {response.status_code}'}
                })
    
    except Exception as e:
        logger.error(f"Error searching Slack: {e}")
        return jsonify(format_error_response(e, 'search_slack')), 500

@slack_enhanced_bp.route('/api/integrations/slack/health', methods=['GET'])
async def health_check():
    """Slack service health check"""
    try:
        if not SLACK_SERVICE_AVAILABLE:
            return jsonify({
                'status': 'unhealthy',
                'error': 'Slack service not available',
                'timestamp': datetime.utcnow().isoformat()
            })
        
        # Test Slack API connectivity
        async with httpx.AsyncClient() as client:
            response = await client.get(f'{SLACK_API_BASE_URL}/api.test', timeout=5)
            
            if response.status_code == 200:
                return jsonify({
                    'status': 'healthy',
                    'message': 'Slack API is accessible',
                    'service_available': SLACK_SERVICE_AVAILABLE,
                    'database_available': SLACK_DB_AVAILABLE,
                    'timestamp': datetime.utcnow().isoformat()
                })
            else:
                return jsonify({
                    'status': 'degraded',
                    'error': f'Slack API returned {response.status_code}',
                    'timestamp': datetime.utcnow().isoformat()
                })
    
    except Exception as e:
        return jsonify({
            'status': 'unhealthy',
            'error': str(e),
            'timestamp': datetime.utcnow().isoformat()
        })

# Error handlers
@slack_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify({
        'ok': False,
        'error': {
            'code': 'NOT_FOUND',
            'message': 'Endpoint not found'
        }
    }), 404

@slack_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify({
        'ok': False,
        'error': {
            'code': 'INTERNAL_ERROR',
            'message': 'Internal server error'
        }
    }), 500