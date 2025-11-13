"""
WhatsApp Business Integration for Atom Platform

This module provides comprehensive integration with the WhatsApp Business API,
enabling businesses to send/receive messages, manage customer communications,
and automate customer support workflows through the Atom platform.

Key Features:
- Send and receive WhatsApp messages
- Manage customer contacts and conversations
- Template message management
- Automated responses and workflows
- Message analytics and reporting
- Integration with existing Atom services
"""

import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin

import psycopg2
import requests
from flask import Blueprint, current_app, jsonify, request
from psycopg2.extras import RealDictCursor

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
whatsapp_bp = Blueprint("whatsapp", __name__, url_prefix="/api/whatsapp")


class WhatsAppBusinessIntegration:
    """WhatsApp Business API integration class"""

    def __init__(self):
        self.base_url = "https://graph.facebook.com/v18.0"
        self.access_token = None
        self.phone_number_id = None
        self.webhook_verify_token = None
        self.db_connection = None

    def initialize(self, config: Dict[str, Any]):
        """Initialize WhatsApp integration with configuration"""
        try:
            self.access_token = config.get("access_token")
            self.phone_number_id = config.get("phone_number_id")
            self.webhook_verify_token = config.get("webhook_verify_token")

            # Check if this is demo mode
            is_demo = config.get("is_demo", False)

            # Initialize database connection (optional in demo mode)
            db_config = config.get("database", {})
            try:
                self.db_connection = psycopg2.connect(
                    host=db_config.get("host", "localhost"),
                    database=db_config.get("database", "atom_development"),
                    user=db_config.get("user", "postgres"),
                    password=db_config.get("password", ""),
                    cursor_factory=RealDictCursor,
                )

                # Create necessary tables if they don't exist
                self._create_tables()
                logger.info(
                    "WhatsApp Business Integration database initialized successfully"
                )

            except Exception as db_error:
                if is_demo:
                    logger.warning(
                        f"Database connection failed in demo mode: {str(db_error)}"
                    )
                    logger.info(
                        "WhatsApp Business Integration running in demo mode without database"
                    )
                    self.db_connection = None
                else:
                    logger.error(
                        f"Failed to initialize WhatsApp database connection: {str(db_error)}"
                    )
                    return False

            logger.info("WhatsApp Business Integration initialized successfully")
            return True

        except Exception as e:
            logger.error(f"Failed to initialize WhatsApp integration: {str(e)}")
            return False

    def _create_tables(self):
        """Create database tables for WhatsApp integration"""
        if not self.db_connection:
            logger.warning("Skipping table creation - no database connection")
            return

        try:
            with self.db_connection.cursor() as cursor:
                # Contacts table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS whatsapp_contacts (
                        id SERIAL PRIMARY KEY,
                        whatsapp_id VARCHAR(50) UNIQUE NOT NULL,
                        name VARCHAR(255),
                        phone_number VARCHAR(20),
                        profile_picture_url TEXT,
                        about TEXT,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Messages table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS whatsapp_messages (
                        id SERIAL PRIMARY KEY,
                        message_id VARCHAR(100) UNIQUE NOT NULL,
                        whatsapp_id VARCHAR(50) NOT NULL,
                        message_type VARCHAR(20) NOT NULL,
                        content JSONB NOT NULL,
                        direction VARCHAR(10) NOT NULL, -- 'inbound' or 'outbound'
                        status VARCHAR(20) DEFAULT 'sent',
                        timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (whatsapp_id) REFERENCES whatsapp_contacts(whatsapp_id)
                    )
                """)

                # Templates table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS whatsapp_templates (
                        id SERIAL PRIMARY KEY,
                        template_name VARCHAR(100) NOT NULL,
                        category VARCHAR(50) NOT NULL,
                        language_code VARCHAR(10) NOT NULL,
                        components JSONB NOT NULL,
                        status VARCHAR(20) DEFAULT 'active',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)

                # Conversations table
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS whatsapp_conversations (
                        id SERIAL PRIMARY KEY,
                        conversation_id VARCHAR(100) UNIQUE NOT NULL,
                        whatsapp_id VARCHAR(50) NOT NULL,
                        status VARCHAR(20) DEFAULT 'active',
                        last_message_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        metadata JSONB,
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                        FOREIGN KEY (whatsapp_id) REFERENCES whatsapp_contacts(whatsapp_id)
                    )
                """)

                self.db_connection.commit()
                logger.info("WhatsApp database tables created/verified successfully")

        except Exception as e:
            logger.error(f"Failed to create WhatsApp tables: {str(e)}")
            self.db_connection.rollback()
            raise

    def send_message(
        self, to: str, message_type: str, content: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Send a WhatsApp message

        Args:
            to: Recipient phone number (with country code)
            message_type: Type of message ('text', 'template', 'media', 'interactive')
            content: Message content based on type

        Returns:
            API response with message details
        """
        try:
            url = f"{self.base_url}/{self.phone_number_id}/messages"

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json",
            }

            # Prepare message payload based on type
            if message_type == "text":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "text",
                    "text": content,
                }
            elif message_type == "template":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "template",
                    "template": content,
                }
            elif message_type == "media":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": content.get("media_type", "image"),
                    content.get("media_type", "image"): content,
                }
            elif message_type == "interactive":
                payload = {
                    "messaging_product": "whatsapp",
                    "to": to,
                    "type": "interactive",
                    "interactive": content,
                }
            else:
                raise ValueError(f"Unsupported message type: {message_type}")

            response = requests.post(url, headers=headers, json=payload)
            response_data = response.json()

            if response.status_code == 200:
                # Store message in database
                self._store_message(
                    message_id=response_data.get("messages", [{}])[0].get("id"),
                    whatsapp_id=to,
                    message_type=message_type,
                    content=content,
                    direction="outbound",
                    status="sent",
                )

                logger.info(f"WhatsApp message sent successfully to {to}")
                return {
                    "success": True,
                    "message_id": response_data.get("messages", [{}])[0].get("id"),
                    "status": "sent",
                }
            else:
                logger.error(f"Failed to send WhatsApp message: {response_data}")
                return {"success": False, "error": response_data}

        except Exception as e:
            logger.error(f"Error sending WhatsApp message: {str(e)}")
            return {"success": False, "error": str(e)}

    def get_conversations(
        self, limit: int = 50, offset: int = 0
    ) -> List[Dict[str, Any]]:
        """
        Get WhatsApp conversations

        Args:
            limit: Maximum number of conversations to retrieve
            offset: Number of conversations to skip

        Returns:
            List of conversations with metadata
        """
        try:
            with self.db_connection.cursor() as cursor:
                query = """
                    SELECT wc.*, w.name, w.phone_number,
                           COUNT(wm.id) as message_count,
                           MAX(wm.timestamp) as last_message_time
                    FROM whatsapp_conversations wc
                    JOIN whatsapp_contacts w ON wc.whatsapp_id = w.whatsapp_id
                    LEFT JOIN whatsapp_messages wm ON wc.whatsapp_id = wm.whatsapp_id
                    GROUP BY wc.id, w.whatsapp_id, w.name, w.phone_number
                    ORDER BY wc.last_message_at DESC
                    LIMIT %s OFFSET %s
                """

                cursor.execute(query, (limit, offset))
                conversations = cursor.fetchall()

                return [dict(conv) for conv in conversations]

        except Exception as e:
            logger.error(f"Error getting conversations: {str(e)}")
            return []

    def get_messages(self, whatsapp_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get messages for a specific WhatsApp contact

        Args:
            whatsapp_id: WhatsApp contact ID
            limit: Maximum number of messages to retrieve

        Returns:
            List of messages
        """
        try:
            with self.db_connection.cursor() as cursor:
                query = """
                    SELECT * FROM whatsapp_messages
                    WHERE whatsapp_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """

                cursor.execute(query, (whatsapp_id, limit))
                messages = cursor.fetchall()

                return [dict(msg) for msg in messages]

        except Exception as e:
            logger.error(f"Error getting messages: {str(e)}")
            return []

    def create_template(
        self,
        template_name: str,
        category: str,
        language_code: str,
        components: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """
        Create a message template

        Args:
            template_name: Name of the template
            category: Template category (UTILITY, MARKETING, AUTHENTICATION)
            language_code: Language code (e.g., 'en', 'es', 'fr')
            components: Template components structure

        Returns:
            Template creation response
        """
        try:
            with self.db_connection.cursor() as cursor:
                query = """
                    INSERT INTO whatsapp_templates
                    (template_name, category, language_code, components)
                    VALUES (%s, %s, %s, %s)
                    RETURNING id
                """

                cursor.execute(
                    query,
                    (template_name, category, language_code, json.dumps(components)),
                )
                template_id = cursor.fetchone()[0]
                self.db_connection.commit()

                logger.info(f"WhatsApp template created: {template_name}")
                return {
                    "success": True,
                    "template_id": template_id,
                    "template_name": template_name,
                }

        except Exception as e:
            logger.error(f"Error creating template: {str(e)}")
            self.db_connection.rollback()
            return {"success": False, "error": str(e)}

    def get_analytics(self, start_date: datetime, end_date: datetime) -> Dict[str, Any]:
        """
        Get WhatsApp analytics and metrics

        Args:
            start_date: Start date for analytics
            end_date: End date for analytics

        Returns:
            Analytics data
        """
        try:
            with self.db_connection.cursor() as cursor:
                # Message statistics
                cursor.execute(
                    """
                    SELECT
                        direction,
                        message_type,
                        status,
                        COUNT(*) as count
                    FROM whatsapp_messages
                    WHERE timestamp BETWEEN %s AND %s
                    GROUP BY direction, message_type, status
                """,
                    (start_date, end_date),
                )

                message_stats = cursor.fetchall()

                # Conversation statistics
                cursor.execute(
                    """
                    SELECT
                        COUNT(*) as total_conversations,
                        COUNT(CASE WHEN last_message_at > NOW() - INTERVAL '7 days' THEN 1 END) as active_conversations
                    FROM whatsapp_conversations
                    WHERE created_at BETWEEN %s AND %s
                """,
                    (start_date, end_date),
                )

                conversation_stats = cursor.fetchone()

                # Contact growth
                cursor.execute(
                    """
                    SELECT
                        DATE(created_at) as date,
                        COUNT(*) as new_contacts
                    FROM whatsapp_contacts
                    WHERE created_at BETWEEN %s AND %s
                    GROUP BY DATE(created_at)
                    ORDER BY date
                """,
                    (start_date, end_date),
                )

                contact_growth = cursor.fetchall()

                return {
                    "message_statistics": [dict(stat) for stat in message_stats],
                    "conversation_statistics": dict(conversation_stats),
                    "contact_growth": [dict(growth) for growth in contact_growth],
                }

        except Exception as e:
            logger.error(f"Error getting analytics: {str(e)}")
            return {}

    def _store_message(
        self,
        message_id: str,
        whatsapp_id: str,
        message_type: str,
        content: Dict[str, Any],
        direction: str,
        status: str,
    ):
        """Store message in database"""
        try:
            with self.db_connection.cursor() as cursor:
                # Ensure contact exists
                cursor.execute(
                    """
                    INSERT INTO whatsapp_contacts (whatsapp_id)
                    VALUES (%s)
                    ON CONFLICT (whatsapp_id) DO NOTHING
                """,
                    (whatsapp_id,),
                )

                # Store message
                cursor.execute(
                    """
                    INSERT INTO whatsapp_messages
                    (message_id, whatsapp_id, message_type, content, direction, status)
                    VALUES (%s, %s, %s, %s, %s, %s)
                    ON CONFLICT (message_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        timestamp = CURRENT_TIMESTAMP
                """,
                    (
                        message_id,
                        whatsapp_id,
                        message_type,
                        json.dumps(content),
                        direction,
                        status,
                    ),
                )

                # Update or create conversation
                cursor.execute(
                    """
                    INSERT INTO whatsapp_conversations (conversation_id, whatsapp_id, last_message_at)
                    VALUES (%s, %s, CURRENT_TIMESTAMP)
                    ON CONFLICT (conversation_id) DO UPDATE
                    SET last_message_at = CURRENT_TIMESTAMP,
                        updated_at = CURRENT_TIMESTAMP
                """,
                    (
                        f"conv_{whatsapp_id}_{datetime.now().strftime('%Y%m%d')}",
                        whatsapp_id,
                    ),
                )

                self.db_connection.commit()

        except Exception as e:
            logger.error(f"Error storing message: {str(e)}")
            self.db_connection.rollback()


# Initialize WhatsApp integration
whatsapp_integration = WhatsAppBusinessIntegration()


@whatsapp_bp.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint"""
    try:
        if whatsapp_integration.access_token:
            return jsonify(
                {
                    "status": "healthy",
                    "service": "WhatsApp Business API",
                    "timestamp": datetime.now().isoformat(),
                }
            )
        else:
            return jsonify(
                {"status": "not_configured", "service": "WhatsApp Business API"}
            ), 503
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 500


@whatsapp_bp.route("/send", methods=["POST"])
def send_message():
    """Send a WhatsApp message"""
    try:
        data = request.get_json()

        # Validate required fields
        if not all(k in data for k in ["to", "type", "content"]):
            return jsonify(
                {
                    "success": False,
                    "error": "Missing required fields: to, type, content",
                }
            ), 400

        result = whatsapp_integration.send_message(
            to=data["to"], message_type=data["type"], content=data["content"]
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in send_message endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@whatsapp_bp.route("/conversations", methods=["GET"])
def get_conversations():
    """Get WhatsApp conversations"""
    try:
        limit = int(request.args.get("limit", 50))
        offset = int(request.args.get("offset", 0))

        conversations = whatsapp_integration.get_conversations(limit, offset)

        return jsonify(
            {
                "success": True,
                "conversations": conversations,
                "total": len(conversations),
            }
        )

    except Exception as e:
        logger.error(f"Error in get_conversations endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@whatsapp_bp.route("/messages/<whatsapp_id>", methods=["GET"])
def get_messages(whatsapp_id):
    """Get messages for a specific WhatsApp contact"""
    try:
        limit = int(request.args.get("limit", 100))

        messages = whatsapp_integration.get_messages(whatsapp_id, limit)

        return jsonify({"success": True, "messages": messages, "total": len(messages)})

    except Exception as e:
        logger.error(f"Error in get_messages endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@whatsapp_bp.route("/templates", methods=["POST"])
def create_template():
    """Create a message template"""
    try:
        data = request.get_json()

        # Validate required fields
        if not all(
            k in data
            for k in ["template_name", "category", "language_code", "components"]
        ):
            return jsonify(
                {
                    "success": False,
                    "error": "Missing required fields: template_name, category, language_code, components",
                }
            ), 400

        result = whatsapp_integration.create_template(
            template_name=data["template_name"],
            category=data["category"],
            language_code=data["language_code"],
            components=data["components"],
        )

        return jsonify(result)

    except Exception as e:
        logger.error(f"Error in create_template endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@whatsapp_bp.route("/analytics", methods=["GET"])
def get_analytics():
    """Get WhatsApp analytics"""
    try:
        start_date = request.args.get("start_date")
        end_date = request.args.get("end_date")

        if start_date:
            start_date = datetime.fromisoformat(start_date)
        else:
            start_date = datetime.now() - timedelta(days=30)

        if end_date:
            end_date = datetime.fromisoformat(end_date)
        else:
            end_date = datetime.now()

        analytics = whatsapp_integration.get_analytics(start_date, end_date)

        return jsonify(
            {
                "success": True,
                "analytics": analytics,
                "period": {
                    "start_date": start_date.isoformat(),
                    "end_date": end_date.isoformat(),
                },
            }
        )

    except Exception as e:
        logger.error(f"Error in get_analytics endpoint: {str(e)}")
        return jsonify({"success": False, "error": str(e)}), 500


@whatsapp_bp.route("/webhook", methods=["GET", "POST"])
def webhook():
    """Handle WhatsApp webhook events"""
    try:
        if request.method == "GET":
            # Webhook verification
            mode = request.args.get("hub.mode")
            token = request.args.get("hub.verify_token")
            challenge = request.args.get("hub.challenge")

            if (
                mode == "subscribe"
                and token == whatsapp_integration.webhook_verify_token
            ):
                return challenge, 200
            else:
                return "Verification failed", 403

        else:  # POST
            # Handle incoming messages and events
            data = request.get_json()

            if "entry" in data:
                for entry in data["entry"]:
                    if "changes" in entry:
                        for change in entry["changes"]:
                            if "messages" in change["value"]:
                                for message in change["value"]["messages"]:
                                    # Process incoming message
                                    _process_incoming_message(message)

            return "ok", 200

    except Exception as e:
        logger.error(f"Error in webhook endpoint: {str(e)}")
        return "error", 500


def _process_incoming_message(message: Dict[str, Any]):
    """Process incoming WhatsApp message"""
    try:
        whatsapp_id = message.get("from")
        message_id = message.get("id")
        message_type = message.get("type")

        # Extract content based on message type
        content = {}
        if message_type == "text":
            content = {"body": message.get("text", {}).get("body", "")}
        elif message_type == "image":
            content = {
                "media_id": message.get("image", {}).get("id", ""),
                "caption": message.get("image", {}).get("caption", ""),
            }
        elif message_type == "audio":
            content = {"media_id": message.get("audio", {}).get("id", "")}
        elif message_type == "document":
            content = {
                "media_id": message.get("document", {}).get("id", ""),
                "filename": message.get("document", {}).get("filename", ""),
            }

        # Store incoming message
        whatsapp_integration._store_message(
            message_id=message_id,
            whatsapp_id=whatsapp_id,
            message_type=message_type,
            content=content,
            direction="inbound",
            status="received",
        )

        logger.info(f"Processed incoming message from {whatsapp_id}")

    except Exception as e:
        logger.error(f"Error processing incoming message: {str(e)}")


def initialize_whatsapp_integration(app, config: Dict[str, Any]):
    """Initialize WhatsApp integration with Flask app"""
    try:
        success = whatsapp_integration.initialize(config)
        if success:
            app.register_blueprint(whatsapp_bp)
            logger.info("WhatsApp Business Integration registered successfully")
        else:
            logger.error("Failed to initialize WhatsApp Business Integration")

    except Exception as e:
        logger.error(f"Error registering WhatsApp integration: {str(e)}")


# Export the integration class and initialization function
__all__ = [
    "WhatsAppBusinessIntegration",
    "initialize_whatsapp_integration",
    "whatsapp_bp",
]
