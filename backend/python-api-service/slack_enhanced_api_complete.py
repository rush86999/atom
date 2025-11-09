#!/usr/bin/env python3
"""
Enhanced Slack API Endpoints
Complete API endpoints for advanced Slack operations
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Create blueprint
slack_enhanced_api_bp = Blueprint('slack_enhanced_api', __name__)

@slack_enhanced_api_bp.route('/api/slack/files/upload', methods=['POST'])
async def upload_file():
    """Upload file to Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Get user from request (simplified - use proper auth in production)
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        # Get file data
        file_data = request.files.get('file')
        if not file_data:
            return jsonify({"success": False, "error": "No file provided"}), 400
        
        channels = request.form.get('channels', '').split(',')
        title = request.form.get('title', file_data.filename)
        initial_comment = request.form.get('initial_comment', '')
        
        # Upload file using Slack service
        result = await service.upload_file(
            file_data=file_data,
            channels=channels,
            title=title,
            initial_comment=initial_comment
        )
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error uploading file to Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/files/<file_id>/download', methods=['GET'])
async def download_file(file_id: str):
    """Download file from Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.args.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        # Get file download URL
        result = await service.get_file_download_url(file_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error downloading file from Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/files/<file_id>', methods=['DELETE'])
async def delete_file(file_id: str):
    """Delete file from Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        result = await service.delete_file(file_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 404
            
    except Exception as e:
        logger.error(f"Error deleting file from Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/messages/<message_id>', methods=['PUT'])
async def edit_message(message_id: str):
    """Edit message in Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        channel_id = request.json.get("channel_id")
        text = request.json.get("text")
        
        if not channel_id or not text:
            return jsonify({
                "success": False, 
                "error": "channel_id and text are required"
            }), 400
        
        result = await service.edit_message(channel_id, message_id, text)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error editing message in Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/messages/<message_id>', methods=['DELETE'])
async def delete_message(message_id: str):
    """Delete message from Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        channel_id = request.json.get("channel_id")
        
        if not channel_id:
            return jsonify({
                "success": False, 
                "error": "channel_id is required"
            }), 400
        
        result = await service.delete_message(channel_id, message_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error deleting message from Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/messages/<message_id>/reactions', methods=['POST'])
async def add_reaction(message_id: str):
    """Add reaction to message"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        channel_id = request.json.get("channel_id")
        reaction = request.json.get("reaction")
        
        if not channel_id or not reaction:
            return jsonify({
                "success": False, 
                "error": "channel_id and reaction are required"
            }), 400
        
        result = await service.add_reaction(channel_id, message_id, reaction)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error adding reaction to message: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/messages/<message_id>/reactions/<reaction_name>', methods=['DELETE'])
async def remove_reaction(message_id: str, reaction_name: str):
    """Remove reaction from message"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        channel_id = request.json.get("channel_id")
        
        if not channel_id:
            return jsonify({
                "success": False, 
                "error": "channel_id is required"
            }), 400
        
        result = await service.remove_reaction(channel_id, message_id, reaction_name)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error removing reaction from message: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/channels', methods=['POST'])
async def create_channel():
    """Create new channel"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        name = request.json.get("name")
        is_private = request.json.get("is_private", False)
        purpose = request.json.get("purpose", "")
        
        if not name:
            return jsonify({
                "success": False, 
                "error": "name is required"
            }), 400
        
        result = await service.create_channel(name, is_private, purpose)
        
        if result.get("success"):
            return jsonify(result), 201
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error creating channel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/channels/<channel_id>/join', methods=['POST'])
async def join_channel(channel_id: str):
    """Join channel"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        result = await service.join_channel(channel_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error joining channel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/channels/<channel_id>/leave', methods=['POST'])
async def leave_channel(channel_id: str):
    """Leave channel"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        result = await service.leave_channel(channel_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error leaving channel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/channels/<channel_id>/archive', methods=['POST'])
async def archive_channel(channel_id: str):
    """Archive channel"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        result = await service.archive_channel(channel_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error archiving channel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/channels/<channel_id>/unarchive', methods=['POST'])
async def unarchive_channel(channel_id: str):
    """Unarchive channel"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        result = await service.unarchive_channel(channel_id)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error unarchiving channel: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/search/files', methods=['POST'])
async def search_files():
    """Search files in Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        query = request.json.get("query", "")
        count = request.json.get("count", 50)
        sort = request.json.get("sort", "timestamp_desc")
        
        if not query:
            return jsonify({
                "success": False, 
                "error": "query is required"
            }), 400
        
        result = await service.search_files(query, count, sort)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error searching files in Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/search/users', methods=['POST'])
async def search_users():
    """Search users in Slack"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        query = request.json.get("query", "")
        
        if not query:
            return jsonify({
                "success": False, 
                "error": "query is required"
            }), 400
        
        result = await service.search_users(query)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error searching users in Slack: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/users/presence', methods=['POST'])
async def set_presence():
    """Set user presence"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        presence = request.json.get("presence")  # "auto" or "away"
        
        if not presence or presence not in ["auto", "away"]:
            return jsonify({
                "success": False, 
                "error": "presence must be 'auto' or 'away'"
            }), 400
        
        result = await service.set_presence(presence)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error setting user presence: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/users/status', methods=['POST'])
async def set_status():
    """Set user status"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        status_text = request.json.get("status_text", "")
        status_emoji = request.json.get("status_emoji", "")
        expiration = request.json.get("expiration")  # Unix timestamp
        
        result = await service.set_status(status_text, status_emoji, expiration)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error setting user status: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/conversations/<conversation_id>/mark', methods=['POST'])
async def mark_conversation(conversation_id: str):
    """Mark conversation as read"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.json.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        ts = request.json.get("ts")
        
        result = await service.mark_conversation(conversation_id, ts)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error marking conversation: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_enhanced_api_bp.route('/api/slack/analytics/engagement', methods=['GET'])
async def get_engagement_analytics():
    """Get workspace engagement analytics"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        user_id = request.args.get("user_id", "current")
        
        service = SlackEnhancedService(user_id)
        await service.initialize(db_pool)
        
        days = int(request.args.get("days", 30))
        
        result = await service.get_engagement_analytics(days)
        
        if result.get("success"):
            return jsonify(result), 200
        else:
            return jsonify(result), 400
            
    except Exception as e:
        logger.error(f"Error getting engagement analytics: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

# Export blueprint
__all__ = ['slack_enhanced_api_bp']