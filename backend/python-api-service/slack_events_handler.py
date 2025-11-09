#!/usr/bin/env python3
"""
Slack Events API Handler
Real-time event handling and webhook management for Slack integration
"""

import os
import json
import logging
import asyncio
import hashlib
import hmac
import time
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from flask import Blueprint, request, jsonify
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Create blueprint
slack_events_bp = Blueprint('slack_events', __name__)

# Slack configuration
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")

# In-memory storage for events (use Redis in production)
event_queue = []
webhooks = {}

def verify_slack_signature(request_body: bytes, timestamp: str, signature: str) -> bool:
    """Verify Slack request signature"""
    if not SLACK_SIGNING_SECRET:
        logger.warning("Slack signing secret not configured, skipping verification")
        return True
    
    try:
        # Check if request is too old (5 minutes)
        if abs(int(datetime.now().timestamp()) - int(timestamp)) > 300:
            return False
        
        # Create expected signature
        sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
        expected_signature = "v0=" + hmac.new(
            SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
        
    except Exception as e:
        logger.error(f"Error verifying Slack signature: {e}")
        return False

@slack_events_bp.route('/api/slack/events', methods=['POST'])
async def handle_slack_events():
    """Handle Slack Events API webhooks"""
    try:
        request_body = request.data
        timestamp = request.headers.get('x-slack-request-timestamp')
        signature = request.headers.get('x-slack-signature')
        
        # Verify request signature
        if not verify_slack_signature(request_body, timestamp, signature):
            return jsonify({"error": "Invalid signature"}), 401
        
        event_data = request.get_json()
        
        # Handle URL verification challenge
        if event_data.get("type") == "url_verification":
            challenge = event_data.get("challenge")
            return jsonify({"challenge": challenge})
        
        # Handle actual events
        if event_data.get("type") == "event_callback":
            event = event_data.get("event", {})
            await process_slack_event(event)
            
        # Handle interaction events (buttons, modals, etc.)
        elif event_data.get("type") == "interactive_message":
            await handle_interaction(event_data)
            
        return jsonify({"status": "ok"}), 200
        
    except Exception as e:
        logger.error(f"Error handling Slack event: {e}")
        return jsonify({"error": str(e)}), 500

async def process_slack_event(event: Dict[str, Any]):
    """Process individual Slack event"""
    try:
        event_type = event.get("type")
        event_data = {
            "type": event_type,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "data": event
        }
        
        # Store event in queue (use proper queue in production)
        event_queue.append(event_data)
        
        # Handle specific event types
        if event_type == "message":
            await handle_message_event(event)
        elif event_type == "app_mention":
            await handle_mention_event(event)
        elif event_type == "channel_created":
            await handle_channel_created_event(event)
        elif event_type == "member_joined_channel":
            await handle_member_joined_event(event)
        elif event_type == "reaction_added":
            await handle_reaction_event(event)
        else:
            logger.info(f"Received unhandled event type: {event_type}")
            
        # Log event for analytics
        await log_slack_event(event_type, event)
        
    except Exception as e:
        logger.error(f"Error processing Slack event: {e}")

async def handle_message_event(event: Dict[str, Any]):
    """Handle message events"""
    try:
        user_id = event.get("user")
        channel_id = event.get("channel")
        text = event.get("text", "")
        ts = event.get("ts")
        
        # Skip bot messages
        if event.get("bot_id") or event.get("subtype") == "bot_message":
            return
        
        # Store message in database
        from slack_enhanced_service import SlackEnhancedService
        
        # Get access token for workspace
        # Note: This would need proper user context handling
        logger.info(f"Message from {user_id} in {channel_id}: {text[:100]}...")
        
        # Trigger any automation rules
        await check_message_automation_rules(event)
        
    except Exception as e:
        logger.error(f"Error handling message event: {e}")

async def handle_mention_event(event: Dict[str, Any]):
    """Handle app mention events"""
    try:
        user_id = event.get("user")
        channel_id = event.get("channel")
        text = event.get("text", "")
        
        logger.info(f"App mentioned by {user_id} in {channel_id}")
        
        # Process command from mention
        await process_bot_command(event)
        
    except Exception as e:
        logger.error(f"Error handling mention event: {e}")

async def process_bot_command(event: Dict[str, Any]):
    """Process bot commands from mentions"""
    try:
        text = event.get("text", "")
        user_id = event.get("user")
        channel_id = event.get("channel")
        
        # Extract command after mention
        # This is simplified - use proper parsing in production
        command = text.lower().replace("@atom", "").strip()
        
        if command.startswith("help"):
            await send_help_message(channel_id)
        elif command.startswith("status"):
            await send_status_message(channel_id)
        elif command.startswith("search"):
            query = command.replace("search", "").strip()
            await search_and_send_results(channel_id, query)
        else:
            await send_default_response(channel_id, user_id)
            
    except Exception as e:
        logger.error(f"Error processing bot command: {e}")

async def send_help_message(channel_id: str):
    """Send help message to channel"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        
        # Get a user's service - this needs proper user context
        service = SlackEnhancedService("current")
        
        help_blocks = [
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "*🤖 ATOM Slack Bot Help*\n\nAvailable commands:"
                }
            },
            {
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": "• `@atom help` - Show this help message\n• `@atom status` - Show workspace status\n• `@atom search <query>` - Search messages\n• `@atom files <query>` - Search files\n• `@atom users` - List workspace users"
                }
            }
        ]
        
        await service.send_message(
            channel_id, 
            "Here are the available commands:",
            blocks=help_blocks
        )
        
    except Exception as e:
        logger.error(f"Error sending help message: {e}")

async def send_status_message(channel_id: str):
    """Send workspace status message"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        
        service = SlackEnhancedService("current")
        
        # Get workspace stats
        stats_text = "📊 *Workspace Status*\n\nFetching current statistics..."
        await service.send_message(channel_id, stats_text)
        
    except Exception as e:
        logger.error(f"Error sending status message: {e}")

async def search_and_send_results(channel_id: str, query: str):
    """Search and send results"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        
        service = SlackEnhancedService("current")
        search_results = await service.search_messages(query, count=5)
        
        if search_results.get("success") and search_results.get("data"):
            results_text = f"🔍 *Search Results for '{query}'*\n\n"
            
            for result in search_results["data"]:
                results_text += f"• {result.get('text', '')[:100]}...\n"
                
            await service.send_message(channel_id, results_text)
        else:
            await service.send_message(channel_id, f"No results found for '{query}'")
            
    except Exception as e:
        logger.error(f"Error searching and sending results: {e}")

async def send_default_response(channel_id: str, user_id: str):
    """Send default response for unrecognized commands"""
    try:
        from slack_enhanced_service import SlackEnhancedService
        
        service = SlackEnhancedService("current")
        
        response_text = f"Hi! I'm ATOM. Use `@atom help` to see available commands."
        await service.send_message(channel_id, response_text)
        
    except Exception as e:
        logger.error(f"Error sending default response: {e}")

async def check_message_automation_rules(event: Dict[str, Any]):
    """Check if message triggers any automation rules"""
    try:
        text = event.get("text", "").lower()
        channel_id = event.get("channel")
        user_id = event.get("user")
        
        # Example automation rules
        if "urgent" in text or "asap" in text:
            await flag_urgent_message(event)
        elif "meeting" in text and ("schedule" in text or "setup" in text):
            await suggest_meeting_scheduler(event)
            
    except Exception as e:
        logger.error(f"Error checking automation rules: {e}")

async def flag_urgent_message(event: Dict[str, Any]):
    """Flag urgent message"""
    try:
        channel_id = event.get("channel")
        from slack_enhanced_service import SlackEnhancedService
        
        service = SlackEnhancedService("current")
        await service.add_reaction(channel_id, event.get("ts"), "rotating_light")
        
    except Exception as e:
        logger.error(f"Error flagging urgent message: {e}")

async def suggest_meeting_scheduler(event: Dict[str, Any]):
    """Suggest meeting scheduler"""
    try:
        channel_id = event.get("channel")
        from slack_enhanced_service import SlackEnhancedService
        
        service = SlackEnhancedService("current")
        
        suggestion = "💡 *Meeting Detected*\nWould you like me to help schedule this meeting? Use the meeting scheduler integration."
        await service.send_message(channel_id, suggestion)
        
    except Exception as e:
        logger.error(f"Error suggesting meeting scheduler: {e}")

@slack_events_bp.route('/api/slack/events/webhooks', methods=['GET'])
async def list_webhooks():
    """List configured webhooks"""
    try:
        return jsonify({
            "success": True,
            "data": list(webhooks.values()),
            "total": len(webhooks)
        })
    except Exception as e:
        logger.error(f"Error listing webhooks: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_events_bp.route('/api/slack/events/webhooks', methods=['POST'])
async def create_webhook():
    """Create new webhook subscription"""
    try:
        data = request.get_json()
        
        webhook = {
            "id": f"webhook_{len(webhooks) + 1}",
            "url": data.get("url"),
            "events": data.get("events", []),
            "active": True,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        
        webhooks[webhook["id"]] = webhook
        
        return jsonify({
            "success": True,
            "data": webhook
        }), 201
        
    except Exception as e:
        logger.error(f"Error creating webhook: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_events_bp.route('/api/slack/events/webhooks/<webhook_id>', methods=['DELETE'])
async def delete_webhook(webhook_id: str):
    """Delete webhook subscription"""
    try:
        if webhook_id in webhooks:
            del webhooks[webhook_id]
            return jsonify({
                "success": True,
                "message": f"Webhook {webhook_id} deleted successfully"
            })
        else:
            return jsonify({
                "success": False,
                "error": "Webhook not found"
            }), 404
            
    except Exception as e:
        logger.error(f"Error deleting webhook: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

@slack_events_bp.route('/api/slack/events/queue', methods=['GET'])
async def get_event_queue():
    """Get recent event queue (for debugging)"""
    try:
        # Return last 50 events
        recent_events = event_queue[-50:] if len(event_queue) > 50 else event_queue
        
        return jsonify({
            "success": True,
            "data": recent_events,
            "total": len(recent_events),
            "queue_size": len(event_queue)
        })
    except Exception as e:
        logger.error(f"Error getting event queue: {e}")
        return jsonify({"success": False, "error": str(e)}), 500

async def log_slack_event(event_type: str, event_data: Dict[str, Any]):
    """Log Slack event for analytics"""
    try:
        # In production, store this in database
        logger.info(f"Slack event logged: {event_type}")
        
    except Exception as e:
        logger.error(f"Error logging Slack event: {e}")

async def handle_channel_created_event(event: Dict[str, Any]):
    """Handle channel creation events"""
    try:
        channel = event.get("channel", {})
        channel_id = channel.get("id")
        channel_name = channel.get("name")
        creator = event.get("user")
        
        logger.info(f"Channel created: {channel_name} ({channel_id}) by {creator}")
        
        # Auto-join new channels if bot should be present
        # await auto_join_channel(channel_id)
        
    except Exception as e:
        logger.error(f"Error handling channel created event: {e}")

async def handle_member_joined_event(event: Dict[str, Any]):
    """Handle member joined channel events"""
    try:
        user = event.get("user")
        channel = event.get("channel")
        inviter = event.get("inviter")
        
        logger.info(f"User {user} joined channel {channel} invited by {inviter}")
        
        # Send welcome message if configured
        # await send_welcome_message(channel, user)
        
    except Exception as e:
        logger.error(f"Error handling member joined event: {e}")

async def handle_reaction_event(event: Dict[str, Any]):
    """Handle reaction events"""
    try:
        user = event.get("user")
        reaction = event.get("reaction")
        item = event.get("item", {})
        channel = item.get("channel")
        timestamp = item.get("ts")
        
        logger.info(f"User {user} added reaction {reaction} to message {timestamp} in {channel}")
        
        # Track popular messages
        # await track_message_popularity(channel, timestamp, reaction)
        
    except Exception as e:
        logger.error(f"Error handling reaction event: {e}")

async def handle_interaction(interaction_data: Dict[str, Any]):
    """Handle interactive components (buttons, modals, etc.)"""
    try:
        payload = json.loads(interaction_data.get("payload", "{}"))
        
        callback_id = payload.get("callback_id")
        action = payload.get("actions", [{}])[0]
        
        logger.info(f"Interaction received: {callback_id} - {action}")
        
        # Handle different interaction types
        if callback_id == "help_button":
            await send_help_response(interaction_data)
        elif callback_id == "search_button":
            await handle_search_interaction(interaction_data)
        else:
            logger.info(f"Unhandled interaction: {callback_id}")
            
    except Exception as e:
        logger.error(f"Error handling interaction: {e}")

# Helper functions for initialization
async def init_slack_events_db(db_pool: Pool):
    """Initialize database tables for events"""
    try:
        async with db_pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS slack_events (
                    id SERIAL PRIMARY KEY,
                    event_type VARCHAR(100) NOT NULL,
                    event_data JSONB NOT NULL,
                    processed BOOLEAN DEFAULT FALSE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                    processed_at TIMESTAMP WITH TIME ZONE
                )
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_slack_events_type 
                ON slack_events(event_type)
            """)
            
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_slack_events_created 
                ON slack_events(created_at)
            """)
            
        logger.info("Slack events database tables initialized")
        
    except Exception as e:
        logger.error(f"Error initializing Slack events database: {e}")

def get_event_stats() -> Dict[str, Any]:
    """Get statistics about event processing"""
    try:
        total_events = len(event_queue)
        active_webhooks = len([w for w in webhooks.values() if w.get("active", False)])
        
        return {
            "total_events_processed": total_events,
            "active_webhooks": active_webhooks,
            "webhook_count": len(webhooks),
            "uptime": "Calculate actual uptime in production"
        }
    except Exception as e:
        logger.error(f"Error getting event stats: {e}")
        return {}

# Export blueprint and functions
__all__ = [
    'slack_events_bp',
    'init_slack_events_db',
    'get_event_stats',
    'process_slack_event'
]