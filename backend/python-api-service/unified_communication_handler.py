"""
ATOM Unified Communication Handler
Handles communication across Slack, Teams, and other platforms
"""

import os
import sys
import asyncio
from flask import Blueprint, request, jsonify, current_app
from datetime import datetime
from typing import Dict, Any, List, Optional
from loguru import logger

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    from slack_service_real import real_slack_service
except ImportError:
    logger.warning("Slack service not available")
    real_slack_service = None

try:
    from teams_service_real import teams_service
    real_teams_service = teams_service
except ImportError:
    logger.warning("Teams service not available")
    real_teams_service = None

try:
    from db_oauth_slack import get_user_slack_tokens
except ImportError:
    logger.warning("Slack database handler not available")
    def get_user_slack_tokens(user_id): return None

try:
    from db_oauth_teams import get_user_teams_tokens
except ImportError:
    logger.warning("Teams database handler not available")
    def get_user_teams_tokens(user_id): return None

unified_communication_bp = Blueprint('unified_communication_bp', __name__)

class UnifiedCommunicationService:
    """Service for unified communication across platforms"""
    
    def __init__(self):
        self.services = {
            'slack': real_slack_service,
            'teams': teams_service
        }
    
    async def get_messages_from_platform(self, platform: str, user_id: str, 
                                       channel_id: Optional[str] = None, 
                                       team_id: Optional[str] = None,
                                       limit: int = 50) -> Dict[str, Any]:
        """Get messages from a specific platform"""
        try:
            service = self.services.get(platform)
            if not service:
                return {"ok": False, "error": f"Platform {platform} not supported"}
            
            # Get user tokens and configure service
            if platform == 'slack':
                tokens = await get_user_slack_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Slack not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
                
            elif platform == 'teams':
                tokens = await get_user_teams_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Teams not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
            
            # Get messages
            if platform == 'slack':
                result = await service.get_messages(channel_id, team_id, limit)
            elif platform == 'teams':
                result = await service.get_messages(channel_id, team_id, limit)
            else:
                result = {"ok": False, "error": f"Method not implemented for {platform}"}
            
            return result
            
        except Exception as e:
            logger.error(f"Unified: Get messages error for {platform}: {e}")
            return {"ok": False, "error": str(e)}
    
    async def send_message_to_platform(self, platform: str, user_id: str,
                                      channel_id: str, content: str,
                                      team_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a specific platform"""
        try:
            service = self.services.get(platform)
            if not service:
                return {"ok": False, "error": f"Platform {platform} not supported"}
            
            # Get user tokens and configure service
            if platform == 'slack':
                tokens = await get_user_slack_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Slack not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
                
            elif platform == 'teams':
                tokens = await get_user_teams_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Teams not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
            
            # Send message
            if platform == 'slack':
                result = await service.send_message(channel_id, content, team_id)
            elif platform == 'teams':
                result = await service.send_message(channel_id, content, team_id)
            else:
                result = {"ok": False, "error": f"Method not implemented for {platform}"}
            
            return result
            
        except Exception as e:
            logger.error(f"Unified: Send message error for {platform}: {e}")
            return {"ok": False, "error": str(e)}
    
    async def get_channels_from_platform(self, platform: str, user_id: str,
                                       team_id: Optional[str] = None) -> Dict[str, Any]:
        """Get channels from a specific platform"""
        try:
            service = self.services.get(platform)
            if not service:
                return {"ok": False, "error": f"Platform {platform} not supported"}
            
            # Get user tokens and configure service
            if platform == 'slack':
                tokens = await get_user_slack_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Slack not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
                
            elif platform == 'teams':
                tokens = await get_user_teams_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Teams not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
            
            # Get channels
            if platform == 'slack':
                result = await service.get_channels(team_id, user_id)
            elif platform == 'teams':
                result = await service.get_channels(team_id)
            else:
                result = {"ok": False, "error": f"Method not implemented for {platform}"}
            
            return result
            
        except Exception as e:
            logger.error(f"Unified: Get channels error for {platform}: {e}")
            return {"ok": False, "error": str(e)}
    
    async def get_teams_from_platform(self, platform: str, user_id: str) -> Dict[str, Any]:
        """Get teams/workspaces from a specific platform"""
        try:
            service = self.services.get(platform)
            if not service:
                return {"ok": False, "error": f"Platform {platform} not supported"}
            
            # Get user tokens and configure service
            if platform == 'slack':
                tokens = await get_user_slack_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Slack not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
                
            elif platform == 'teams':
                tokens = await get_user_teams_tokens(user_id)
                if not tokens or not tokens.get('access_token'):
                    return {"ok": False, "error": "Teams not authenticated"}
                service._access_token = tokens['access_token']
                service._refresh_token = tokens.get('refresh_token')
            
            # Get teams/workspaces
            if platform == 'slack':
                result = await service.get_workspaces(user_id)
            elif platform == 'teams':
                result = await service.get_teams()
            else:
                result = {"ok": False, "error": f"Method not implemented for {platform}"}
            
            return result
            
        except Exception as e:
            logger.error(f"Unified: Get teams error for {platform}: {e}")
            return {"ok": False, "error": str(e)}

# Initialize unified service
unified_service = UnifiedCommunicationService()

def run_async(coro):
    """Helper to run async functions in Flask routes"""
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)

@unified_communication_bp.route('/api/communication/messages', methods=['POST'])
def get_unified_messages():
    """Get messages from multiple communication platforms"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        platforms = data.get('platforms', ['slack', 'teams'])
        channel_id = data.get('channel_id')
        team_id = data.get('team_id')
        limit = data.get('limit', 50)
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        all_messages = []
        errors = {}
        
        for platform in platforms:
            try:
                result = run_async(
                    unified_service.get_messages_from_platform(
                        platform, user_id, channel_id, team_id, limit
                    )
                )
                if result.get('ok'):
                    # Transform messages to unified format
                    platform_messages = []
                    for msg in result.get('messages', []):
                        platform_messages.append({
                            "id": msg.get('id'),
                            "platform": platform,
                            "from": msg.get('from'),
                            "subject": msg.get('subject'),
                            "preview": msg.get('preview'),
                            "content": msg.get('content'),
                            "timestamp": msg.get('timestamp'),
                            "unread": msg.get('unread', False),
                            "priority": msg.get('priority', 'normal'),
                            "status": msg.get('status', 'received'),
                            "attachments": msg.get('attachments', []),
                            "reactions": msg.get('reactions', {}),
                            "reply_count": msg.get('reply_count', 0),
                            "channel_id": msg.get('channel_id'),
                            "team_id": msg.get('team_id')
                        })
                    all_messages.extend(platform_messages)
                else:
                    errors[platform] = result.get('error', 'Unknown error')
            except Exception as e:
                logger.error(f"Error getting messages from {platform}: {e}")
                errors[platform] = str(e)
        
        # Sort by timestamp (newest first)
        all_messages.sort(key=lambda x: x.get('timestamp', ''), reverse=True)
        
        return jsonify({
            "ok": True,
            "messages": all_messages,
            "total_count": len(all_messages),
            "platforms": platforms,
            "errors": errors,
            "retrieved_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Unified messages endpoint error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@unified_communication_bp.route('/api/communication/send', methods=['POST'])
def send_unified_message():
    """Send message to a specific communication platform"""
    try:
        data = request.get_json()
        platform = data.get('platform')
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        content = data.get('content')
        team_id = data.get('team_id')
        
        if not all([platform, user_id, channel_id, content]):
            return jsonify({"ok": False, "error": "platform, user_id, channel_id, and content are required"}), 400
        
        if platform not in ['slack', 'teams']:
            return jsonify({"ok": False, "error": f"Platform {platform} not supported"}), 400
        
        result = run_async(
            unified_service.send_message_to_platform(
                platform, user_id, channel_id, content, team_id
            )
        )
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"Unified send endpoint error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@unified_communication_bp.route('/api/communication/channels', methods=['POST'])
def get_unified_channels():
    """Get channels from multiple communication platforms"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        platforms = data.get('platforms', ['slack', 'teams'])
        team_id = data.get('team_id')
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        all_channels = []
        errors = {}
        
        for platform in platforms:
            try:
                result = run_async(
                    unified_service.get_channels_from_platform(
                        platform, user_id, team_id
                    )
                )
                if result.get('ok'):
                    # Transform channels to unified format
                    platform_channels = []
                    for channel in result.get('channels', []):
                        platform_channels.append({
                            "id": channel.get('id'),
                            "platform": platform,
                            "name": channel.get('name'),
                            "display_name": channel.get('display_name'),
                            "team_id": channel.get('team_id'),
                            "channel_type": channel.get('channel_type'),
                            "purpose": channel.get('purpose'),
                            "member_count": channel.get('member_count', 0),
                            "is_private": channel.get('is_private', False),
                            "is_archived": channel.get('is_archived', False)
                        })
                    all_channels.extend(platform_channels)
                else:
                    errors[platform] = result.get('error', 'Unknown error')
            except Exception as e:
                logger.error(f"Error getting channels from {platform}: {e}")
                errors[platform] = str(e)
        
        return jsonify({
            "ok": True,
            "channels": all_channels,
            "total_count": len(all_channels),
            "platforms": platforms,
            "errors": errors,
            "retrieved_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Unified channels endpoint error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@unified_communication_bp.route('/api/communication/teams', methods=['POST'])
def get_unified_teams():
    """Get teams/workspaces from multiple communication platforms"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        platforms = data.get('platforms', ['slack', 'teams'])
        
        if not user_id:
            return jsonify({"ok": False, "error": "user_id is required"}), 400
        
        all_teams = []
        errors = {}
        
        for platform in platforms:
            try:
                result = run_async(
                    unified_service.get_teams_from_platform(platform, user_id)
                )
                if result.get('ok'):
                    # Transform teams to unified format
                    platform_teams = []
                    for team in result.get('teams', []):
                        platform_teams.append({
                            "id": team.get('id'),
                            "platform": platform,
                            "name": team.get('name'),
                            "description": team.get('description'),
                            "team_type": team.get('team_type', 'standard'),
                            "visibility": team.get('visibility', 'public'),
                            "member_count": team.get('member_count', 0),
                            "is_archived": team.get('is_archived', False),
                            "web_url": team.get('web_url', '')
                        })
                    all_teams.extend(platform_teams)
                else:
                    errors[platform] = result.get('error', 'Unknown error')
            except Exception as e:
                logger.error(f"Error getting teams from {platform}: {e}")
                errors[platform] = str(e)
        
        return jsonify({
            "ok": True,
            "teams": all_teams,
            "total_count": len(all_teams),
            "platforms": platforms,
            "errors": errors,
            "retrieved_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Unified teams endpoint error: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500

@unified_communication_bp.route('/api/communication/health', methods=['GET'])
def health_check():
    """Check health of all communication services"""
    try:
        health_status = {}
        
        for platform, service in unified_service.services.items():
            try:
                if hasattr(service, 'health_check'):
                    result = run_async(service.health_check())
                    health_status[platform] = result
                else:
                    health_status[platform] = {"status": "unknown", "error": "No health check method"}
            except Exception as e:
                health_status[platform] = {"status": "unhealthy", "error": str(e)}
        
        overall_healthy = all(
            status.get('status') == 'healthy' 
            for status in health_status.values()
        )
        
        return jsonify({
            "status": "healthy" if overall_healthy else "unhealthy",
            "services": health_status,
            "checked_at": datetime.utcnow().isoformat()
        })
        
    except Exception as e:
        logger.error(f"Health check endpoint error: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": str(e),
            "checked_at": datetime.utcnow().isoformat()
        }), 500