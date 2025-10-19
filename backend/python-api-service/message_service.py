"""
Message Service for Atom Personal Assistant

This service provides unified message management across multiple platforms:
- Email (Gmail, Outlook)
- Chat (Slack, Teams, Discord)
- SMS (Twilio)
- Unified inbox and search
"""

import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from enum import Enum

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Message type enumeration"""

    EMAIL = "email"
    SLACK = "slack"
    TEAMS = "teams"
    DISCORD = "discord"
    SMS = "sms"
    WHATSAPP = "whatsapp"


class MessageStatus(Enum):
    """Message status enumeration"""

    UNREAD = "unread"
    READ = "read"
    ARCHIVED = "archived"
    DELETED = "deleted"
    DRAFT = "draft"
    SENT = "sent"
    FAILED = "failed"


class MessagePriority(Enum):
    """Message priority enumeration"""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


class MessageService:
    """Service for message management operations"""

    def __init__(self, db_pool=None):
        self.db_pool = db_pool
        self.integrations = {}  # Will hold message integration instances

    async def get_messages(
        self,
        user_id: str,
        message_type: Optional[str] = None,
        status: Optional[str] = None,
        priority: Optional[str] = None,
        sender: Optional[str] = None,
        search_query: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """Get messages with filtering options"""
        try:
            messages = []

            # Get messages from database
            if self.db_pool:
                messages = await self._get_messages_from_db(
                    user_id, message_type, status, priority, sender,
                    search_query, date_range, limit, offset
                )
            else:
                # Mock data for demonstration
                messages = self._generate_mock_messages(user_id)

            # Apply filters
            filtered_messages = self._apply_message_filters(
                messages, message_type, status, priority, sender, search_query, date_range
            )

            # Get messages from integrated platforms
            integrated_messages = await self._get_integrated_messages(
                user_id, message_type, status, priority, sender, search_query, date_range
            )
            filtered_messages.extend(integrated_messages)

            # Sort by timestamp (newest first)
            filtered_messages.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

            return filtered_messages[:limit]

        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []

    async def send_message(
        self,
        user_id: str,
        message_data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Send a new message"""
        try:
            message = {
                "id": f"msg_{datetime.now().timestamp()}",
                "user_id": user_id,
                "type": message_data.get("type", MessageType.EMAIL.value),
                "subject": message_data.get("subject", ""),
                "body": message_data.get("body", ""),
                "sender": message_data.get("sender", user_id),
                "recipients": message_data.get("recipients", []),
                "cc": message_data.get("cc", []),
                "bcc": message_data.get("bcc", []),
                "attachments": message_data.get("attachments", []),
                "priority": message_data.get("priority", MessagePriority.NORMAL.value),
                "status": MessageStatus.SENT.value,
                "thread_id": message_data.get("thread_id"),
                "external_id": message_data.get("external_id"),
                "external_platform": message_data.get("external_platform"),
                "timestamp": datetime.now().isoformat(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat()
            }

            # Validate required fields
            if not message["body"]:
                raise ValueError("Message body is required")
            if not message["recipients"]:
                raise ValueError("At least one recipient is required")

            # Validate message type and status
            if message["type"] not in [t.value for t in MessageType]:
                raise ValueError(f"Invalid message type: {message['type']}")
            if message["priority"] not in [p.value for p in MessagePriority]:
                raise ValueError(f"Invalid message priority: {message['priority']}")

            # Send via appropriate platform
            if message["external_platform"]:
                await self._send_via_external_platform(message)
            else:
                # Default to email if no platform specified
                await self._send_email(message)

            # Save to database if available
            if self.db_pool:
                await self._save_message_to_db(message)

            logger.info(f"Sent message to {len(message['recipients'])} recipients for user {user_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            raise

    async def mark_as_read(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Mark a message as read"""
        try:
            message = await self._get_message_by_id(user_id, message_id)
            if not message:
                raise ValueError(f"Message {message_id} not found")

            message["status"] = MessageStatus.READ.value
            message["read_at"] = datetime.now().isoformat()
            message["updated_at"] = datetime.now().isoformat()

            # Save updates
            if self.db_pool:
                await self._update_message_in_db(message)

            # Sync to external platforms if this is an integrated message
            if message.get("external_platform"):
                await self._sync_message_to_external_platform(message)

            logger.info(f"Marked message as read for user {user_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to mark message as read: {e}")
            raise

    async def archive_message(self, user_id: str, message_id: str) -> Dict[str, Any]:
        """Archive a message"""
        try:
            message = await self._get_message_by_id(user_id, message_id)
            if not message:
                raise ValueError(f"Message {message_id} not found")

            message["status"] = MessageStatus.ARCHIVED.value
            message["archived_at"] = datetime.now().isoformat()
            message["updated_at"] = datetime.now().isoformat()

            # Save updates
            if self.db_pool:
                await self._update_message_in_db(message)

            # Sync to external platforms
            if message.get("external_platform"):
                await self._sync_message_to_external_platform(message)

            logger.info(f"Archived message for user {user_id}")
            return message

        except Exception as e:
            logger.error(f"Failed to archive message: {e}")
            raise

    async def delete_message(self, user_id: str, message_id: str) -> bool:
        """Delete a message"""
        try:
            message = await self._get_message_by_id(user_id, message_id)
            if not message:
                return False

            # Delete from external platform first if integrated
            if message.get("external_platform"):
                await self._delete_message_from_external_platform(message)

            if self.db_pool:
                await self._delete_message_from_db(user_id, message_id)

            logger.info(f"Deleted message for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to delete message: {e}")
            return False

    async def search_messages(
        self,
        user_id: str,
        query: str,
        message_type: Optional[str] = None,
        date_range: Optional[Dict[str, str]] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Search messages across all platforms"""
        try:
            results = []

            # Search in database
            if self.db_pool:
                db_results = await self._search_messages_in_db(
                    user_id, query, message_type, date_range, limit
                )
                results.extend(db_results)

            # Search in integrated platforms
            for platform, integration in self.integrations.items():
                try:
                    platform_results = await integration.search_messages(
                        user_id, query, message_type, date_range, limit
                    )
                    results.extend(platform_results)
                except Exception as e:
                    logger.error(f"Failed to search messages in {platform}: {e}")
                    continue

            # Remove duplicates and sort by relevance score
            unique_results = self._deduplicate_messages(results)
            unique_results.sort(key=lambda x: x.get("relevance_score", 0), reverse=True)

            return unique_results[:limit]

        except Exception as e:
            logger.error(f"Failed to search messages: {e}")
            return []

    async def get_message_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get message statistics for a user"""
        try:
            messages = await self.get_messages(user_id, limit=1000)  # Get all messages

            stats = {
                "total_messages": len(messages),
                "unread_messages": len([
                    m for m in messages
                    if m.get("status") == MessageStatus.UNREAD.value
                ]),
                "email_messages": len([
                    m for m in messages
                    if m.get("type") == MessageType.EMAIL.value
                ]),
                "slack_messages": len([
                    m for m in messages
                    if m.get("type") == MessageType.SLACK.value
                ]),
                "teams_messages": len([
                    m for m in messages
                    if m.get("type") == MessageType.TEAMS.value
                ]),
                "high_priority_messages": len([
                    m for m in messages
                    if m.get("priority") in [MessagePriority.HIGH.value, MessagePriority.URGENT.value]
                ]),
                "messages_today": len([
                    m for m in messages
                    if self._is_today(m.get("timestamp"))
                ]),
                "messages_this_week": len([
                    m for m in messages
                    if self._is_this_week(m.get("timestamp"))
                ]),
            }

            # Calculate response rate (for sent messages)
            sent_messages = [
                m for m in messages
                if m.get("status") == MessageStatus.SENT.value
            ]
            if sent_messages:
                responded_messages = [
                    m for m in sent_messages
                    if m.get("has_response", False)
                ]
                stats["response_rate"] = round(
                    (len(responded_messages) / len(sent_messages)) * 100, 2
                )
            else:
                stats["response_rate"] = 0

            return stats

        except Exception as e:
            logger.error(f"Failed to get message statistics: {e}")
            return {}

    async def sync_external_messages(self, user_id: str, platform: str) -> Dict[str, Any]:
        """Sync messages from external platform"""
        try:
            if platform not in self.integrations:
                raise ValueError(f"Platform {platform} not integrated")

            integration = self.integrations[platform]
            external_messages = await integration.get_messages(user_id)

            synced_count = 0
            for external_message in external_messages:
                # Check if message already exists
                existing_message = await self._find_message_by_external_id(
                    user_id, platform, external_message["external_id"]
                )

                if existing_message:
                    # Update existing message
                    await self._update_message_from_external(
                        existing_message["id"], external_message
                    )
                else:
                    # Create new message record
                    external_message["external_platform"] = platform
                    await self._save_message_to_db(external_message)

                synced_count += 1

            return {
                "success": True,
                "platform": platform,
                "messages_synced": synced_count,
                "timestamp": datetime.now().isoformat()
            }

        except Exception as e:
            logger.error(f"Failed to sync messages from {platform}: {e}")
            return {
                "success": False,
                "platform": platform,
                "error": str(e),
                "timestamp": datetime.now().isoformat()
            }

    def _apply_message_filters(
        self,
        messages: List[Dict[str, Any]],
        message_type: Optional[str],
        status: Optional[str],
        priority: Optional[str],
        sender: Optional[str],
        search_query: Optional[str],
        date_range: Optional[Dict[str, str]]
    ) -> List[Dict[str, Any]]:
        """Apply filters to message list"""
        filtered_messages = messages

        if message_type:
            filtered_messages = [
                m for m in filtered_messages
                if m.get("type") == message_type
            ]

        if status:
            filtered_messages = [
                m for m in filtered_messages
                if m.get("status") == status
            ]

        if priority:
            filtered_messages = [
                m for m in filtered_messages
                if m.get("priority") == priority
            ]

        if sender:
            filtered_messages = [
                m for m in filtered_messages
                if sender.lower() in m.get("sender", "").lower()
            ]

        if search_query:
            filtered_messages = [
                m for m in filtered_messages
                if self._message_matches_query(m, search_query)
            ]

        if date_range:
            start_date = date_range.get("start")
            end_date = date_range.get("end")
            filtered_messages = [
                m for m in filtered_messages
                if self._is_date_in_range(m.get("timestamp"), start_date, end_date)
            ]

        return filtered_messages

    def _message_matches_query(self, message: Dict[str, Any], query: str) -> bool:
        """Check if message matches search query"""
        query = query.lower()
        search_fields = [
            message.get("subject", ""),
            message.get("body", ""),
            message.get("sender", ""),
            " ".join(message.get("recipients", [])),
            " ".join(message.get("tags", []))
        ]

        return any(query in field.lower() for field in search_fields)

    def _is_date_in_range(
        self,
        date_str: Optional[str],
        start: Optional[str],
        end: Optional[str]
    ) -> bool:
        """Check if a date is within a range"""
        if not date_str:
            return False

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            if start:
                start_date = datetime.fromisoformat(start.replace("Z", "+00:00"))
                if date < start_date:
                    return False
            if end:
                end_date = datetime.fromisoformat(end.replace("Z", "+00:00"))
                if date > end_date:
                    return False
            return True
        except Exception:
            return False

    def _is_today(self, date_str: Optional[str]) -> bool:
        """Check if date is today"""
        if not date_str:
            return False

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            return date.date() == datetime.now().date()
        except Exception:
            return False

    def _is_this_week(self, date_str: Optional[str]) -> bool:
        """Check if date is this week"""
        if not date_str:
            return False

        try:
            date = datetime.fromisoformat(date_str.replace("Z", "+00:00"))
            today = datetime.now().date()
            start_of_week = today - timedelta(days=today.weekday())
            end_of_week = start_of_week + timedelta(days=6)
            return start_of_week <= date.date() <= end_of_week
        except Exception:
            return False

    def _deduplicate_messages(self, messages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate messages based on external_id or content"""
        seen_ids = set()
        unique_messages = []

        for message in messages:
            message_id = message.get("external_id") or message.get("id")
            if message_id not in seen_ids:
                seen_ids.add(message_id)
                unique_messages.append(message)

        return unique_messages

    def _generate_mock_messages(self, user_id: str) -> List[Dict[str, Any]]:
        """Generate mock messages for testing"""
        sample_senders = [
            "john.doe@company.com",
            "sarah.smith@client.org",
            "team@project.com",
            "alex.jones@partner.net",
            "notifications@system.com"
        ]

        sample_subjects = [
            "Project Update Meeting",
            "Weekly Status Report",
            "Important Announcement",
            "Action Required: Review Documents",
            "Team Lunch This Friday",
            "New Feature Launch",
            "Security Alert",
            "Welcome to the Team!"
        ]

        messages = []
        for i in range(20):
            message_type = MessageType.EMAIL.value if i % 3 == 0 else MessageType.SLACK.value if i % 3 == 1 else MessageType.TEAMS.value
            status = MessageStatus.UNREAD.value if i % 5 == 0 else MessageStatus.READ.value

            messages.append({
                "id": f"msg_{i}",
                "user_id": user_id,
                "type": message_type,
                "subject": sample_subjects[i % len(sample_subjects)],
                "body": f"This is a sample message {i} with some content for testing purposes.",
                "sender": sample_senders[i % len(sample_senders)],
                "recipients": [user_id],
                "priority": MessagePriority.NORMAL.value,
                "status": status,
                "timestamp": (datetime.now() - timedelta(hours=i)).isoformat(),
                "created_at": (datetime.now() - timedelta(hours=i)).isoformat(),
                "updated_at": datetime.now().isoformat()
            })

        return messages

    async def _send_via_external_platform(self, message: Dict[str,
