"""
Unified Message Processor
Normalizes and processes messages from all communication platforms (Slack, Teams, Email)
with unified schema, deduplication, and cross-platform threading.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import hashlib
import logging
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger(__name__)


class MessageType(Enum):
    """Types of messages"""
    TEXT = "text"
    HTML = "html"
    ATTACHMENT = "attachment"
    SYSTEM = "system"
    AUTOMATED = "automated"


class MessagePriority(Enum):
    """Message priority levels"""
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    URGENT = "urgent"


@dataclass
class UnifiedMessage:
    """
    Unified message schema that normalizes all platform messages.

    This is the single source of truth for all messages in the system.
    """
    # Core identifiers
    id: str
    unified_id: str  # Cross-platform unique ID (hash of content + timestamp)
    platform: str  # slack, teams, gmail, outlook
    platform_message_id: str  # Original message ID from platform

    # Content
    content: str
    subject: Optional[str] = None
    content_type: str = "text"  # text, html, markdown

    # Sender/Recipient
    sender_name: str = ""
    sender_email: Optional[str] = None
    sender_platform_id: Optional[str] = None  # Platform-specific sender ID
    recipient: Optional[str] = None

    # Timestamp
    timestamp: Optional[datetime] = None
    timestamp_platform: Optional[str] = None  # Original timestamp string

    # Thread/Conversation
    thread_id: Optional[str] = None
    thread_platform_id: Optional[str] = None  # Platform thread ID
    conversation_id: Optional[str] = None  # Cross-platform conversation ID
    reply_to_message_id: Optional[str] = None

    # Channel/Location context
    channel_id: Optional[str] = None
    channel_name: Optional[str] = None
    channel_type: Optional[str] = None  # channel, chat, email, dm

    # Attachments
    attachments: List[Dict[str, Any]] = field(default_factory=list)
    has_attachments: bool = False

    # Platform-specific metadata
    platform_metadata: Dict[str, Any] = field(default_factory=dict)

    # Classification
    message_type: str = MessageType.TEXT.value
    priority: str = MessagePriority.NORMAL.value
    direction: str = "inbound"  # inbound, outbound, internal

    # Processing flags
    is_processed: bool = False
    is_duplicate: bool = False
    is_cross_posted: bool = False  # Posted to multiple platforms
    related_message_ids: List[str] = field(default_factory=list)  # IDs of related messages

    # Search/Filtering
    tags: List[str] = field(default_factory=list)
    mentions: List[str] = field(default_factory=list)  # @mentions in message
    urls: List[str] = field(default_factory=list)  # URLs extracted from content

    # Status
    status: str = "active"  # active, deleted, archived
    flags: Dict[str, bool] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            "id": self.id,
            "unified_id": self.unified_id,
            "platform": self.platform,
            "platform_message_id": self.platform_message_id,
            "content": self.content,
            "content_type": self.content_type,
            "subject": self.subject,
            "sender_name": self.sender_name,
            "sender_email": self.sender_email,
            "sender_platform_id": self.sender_platform_id,
            "recipient": self.recipient,
            "timestamp": self.timestamp.isoformat() if self.timestamp else None,
            "timestamp_platform": self.timestamp_platform,
            "thread_id": self.thread_id,
            "thread_platform_id": self.thread_platform_id,
            "conversation_id": self.conversation_id,
            "reply_to_message_id": self.reply_to_message_id,
            "channel_id": self.channel_id,
            "channel_name": self.channel_name,
            "channel_type": self.channel_type,
            "attachments": self.attachments,
            "has_attachments": self.has_attachments,
            "platform_metadata": self.platform_metadata,
            "message_type": self.message_type,
            "priority": self.priority,
            "direction": self.direction,
            "is_processed": self.is_processed,
            "is_duplicate": self.is_duplicate,
            "is_cross_posted": self.is_cross_posted,
            "related_message_ids": self.related_message_ids,
            "tags": self.tags,
            "mentions": self.mentions,
            "urls": self.urls,
            "status": self.status,
            "flags": self.flags
        }


class UnifiedMessageProcessor:
    """
    Processes and normalizes messages from all communication platforms.

    Features:
    - Unified schema normalization
    - Deduplication (same message across platforms)
    - Cross-platform threading
    - Content enrichment (URLs, mentions, entities)
    - Similarity detection for cross-posting
    """

    def __init__(self):
        self.processed_messages: Dict[str, UnifiedMessage] = {}
        self.message_hashes: Set[str] = set()  # For deduplication
        self.conversation_threads: Dict[str, List[str]] = {}  # conversation_id -> [message_ids]
        self.cross_platform_map: Dict[str, List[str]] = {}  # unified_id -> [platform_message_ids]

    def generate_unified_id(self, content: str, timestamp: datetime, platform: str) -> str:
        """
        Generate a unified message ID for cross-platform deduplication.

        Uses content hash + timestamp to detect same message across platforms.
        """
        # Normalize content for hashing
        normalized_content = content.lower().strip()

        # Create hash of content + date (not time) for cross-platform matching
        date_str = timestamp.date().isoformat()
        hash_input = f"{platform}:{normalized_content}:{date_str}"

        return hashlib.sha256(hash_input.encode()).hexdigest()[:16]

    def normalize_message(self, raw_message: Dict[str, Any]) -> UnifiedMessage:
        """
        Normalize a raw message from any platform into UnifiedMessage schema.

        Args:
            raw_message: Raw message data from Slack, Teams, Gmail, or Outlook

        Returns:
            UnifiedMessage with normalized schema
        """
        app_type = raw_message.get("app_type", "")
        platform = app_type.replace("microsoft_teams", "teams")

        # Extract content
        content = raw_message.get("content", "")
        content_type = raw_message.get("content_type", "text")
        subject = raw_message.get("subject")

        # Extract sender info
        sender_name = raw_message.get("sender", "Unknown")
        sender_email = raw_message.get("sender_email")
        sender_platform_id = raw_message.get("metadata", {}).get("sender_id")

        # Parse sender name from "Name <email>" format if present
        if "<" in sender_name and ">" in sender_name:
            parts = sender_name.rsplit("<", 1)
            sender_name = parts[0].strip()
            if not sender_email:
                sender_email = parts[1].rstrip(">")
        elif "@" in sender_name and not sender_email:
            # Sender is just an email address
            sender_email = sender_name
            sender_name = sender_name.split("@")[0]

        # Handle different platform sender formats
        if not sender_email and platform == "slack":
            # Slack: sender might be a user ID
            sender_platform_id = sender_name

        # Extract timestamp
        timestamp = raw_message.get("timestamp")
        if isinstance(timestamp, str):
            try:
                timestamp = datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                timestamp = datetime.now()
        elif not isinstance(timestamp, datetime):
            timestamp = datetime.now()

        # Extract thread info
        metadata = raw_message.get("metadata", {})
        thread_id = metadata.get("thread_id")
        thread_platform_id = metadata.get("thread_id")
        conversation_id = metadata.get("conversation_id")

        # Platform-specific thread handling
        if platform == "gmail":
            thread_id = metadata.get("thread_id")
            thread_platform_id = thread_id
            conversation_id = metadata.get("thread_id")  # Gmail uses thread as conversation
        elif platform == "outlook":
            thread_id = metadata.get("conversation_id")
            thread_platform_id = thread_id
            conversation_id = metadata.get("conversation_id")  # Outlook uses conversation_id
        elif platform == "teams":
            thread_id = metadata.get("thread_id")  # Could be chat_id
            thread_platform_id = thread_id

        # Extract channel info
        channel_id = raw_message.get("metadata", {}).get("channel_id")
        channel_name = raw_message.get("metadata", {}).get("channel_name")

        if not channel_name and platform == "teams":
            # Teams might use chat title
            channel_name = raw_message.get("metadata", {}).get("chat_title")

        if not channel_id and platform == "teams":
            channel_id = raw_message.get("recipient")  # For Teams, recipient might be chat ID

        # Extract attachments
        attachments = raw_message.get("attachments", [])
        has_attachments = len(attachments) > 0

        # Extract priority
        priority = raw_message.get("priority", "normal")
        if priority == "high":
            priority = MessagePriority.HIGH.value
        elif priority == "urgent":
            priority = MessagePriority.URGENT.value
        elif priority == "low":
            priority = MessagePriority.LOW.value
        else:
            priority = MessagePriority.NORMAL.value

        # Generate unified ID
        unified_id = self.generate_unified_id(content, timestamp, platform)

        # Create unified message
        unified = UnifiedMessage(
            id=raw_message.get("id", f"{platform}_{timestamp.timestamp()}"),
            unified_id=unified_id,
            platform=platform,
            platform_message_id=raw_message.get("id", ""),
            content=content,
            content_type=content_type,
            subject=subject,
            sender_name=sender_name,
            sender_email=sender_email,
            sender_platform_id=sender_platform_id,
            recipient=raw_message.get("recipient"),
            timestamp=timestamp,
            timestamp_platform=raw_message.get("metadata", {}).get("created_datetime"),
            thread_id=thread_id,
            thread_platform_id=thread_platform_id,
            conversation_id=conversation_id,
            reply_to_message_id=raw_message.get("metadata", {}).get("reply_to_id"),
            channel_id=channel_id,
            channel_name=channel_name,
            channel_type=self._infer_channel_type(platform, raw_message),
            attachments=attachments,
            has_attachments=has_attachments,
            platform_metadata=raw_message.get("metadata", {}),
            message_type=self._infer_message_type(raw_message),
            priority=priority,
            direction=raw_message.get("direction", "inbound"),
            tags=raw_message.get("tags", []),
            status=raw_message.get("status", "active"),
            flags=raw_message.get("flags", {})
        )

        # Enrich with extracted data
        self._enrich_message(unified)

        return unified

    def _infer_channel_type(self, platform: str, raw_message: Dict[str, Any]) -> Optional[str]:
        """Infer channel type from platform and message data"""
        if platform == "slack":
            if raw_message.get("metadata", {}).get("channel_type") == "channel":
                return "channel"
            elif raw_message.get("metadata", {}).get("channel_type") == "im":
                return "dm"
            return "unknown"
        elif platform == "teams":
            chat_type = raw_message.get("metadata", {}).get("chat_type")
            if chat_type == "oneOnOne":
                return "dm"
            elif chat_type == "group":
                return "group_chat"
            elif chat_type == "meeting":
                return "meeting"
            return "teams_channel"
        elif platform in ["gmail", "outlook"]:
            return "email"
        return "unknown"

    def _infer_message_type(self, raw_message: Dict[str, Any]) -> str:
        """Infer message type from content and metadata"""
        content = raw_message.get("content", "")
        attachments = raw_message.get("attachments", [])

        # Check for bot messages without content (system messages)
        if raw_message.get("metadata", {}).get("bot_id") and not content.strip():
            return MessageType.SYSTEM.value

        # Check for attachment-only messages
        if attachments and len(attachments) > 0 and not content.strip():
            return MessageType.ATTACHMENT.value

        # Check for HTML content
        if "<html>" in content.lower() or "<div>" in content.lower():
            return MessageType.HTML.value

        # Default to text message
        return MessageType.TEXT.value

    def _enrich_message(self, message: UnifiedMessage):
        """Enrich message with extracted entities"""
        import re

        # Extract URLs
        url_pattern = r'https?://[^\s<>"{}|\\^`\[\]]+'
        message.urls = re.findall(url_pattern, message.content)

        # Extract mentions (@username, <@user_id>)
        if message.platform == "slack":
            mention_pattern = r'<@(\w+)>'
            message.mentions = re.findall(mention_pattern, message.content)
        elif message.platform in ["gmail", "outlook"]:
            # Email mentions
            mention_pattern = r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
            message.mentions = re.findall(mention_pattern, message.content)

        # Add platform tag
        message.tags.append(message.platform)

        # Add type tag
        if message.has_attachments:
            message.tags.append("has_attachments")

    def detect_duplicates(self, messages: List[UnifiedMessage]) -> Tuple[List[UnifiedMessage], Dict[str, List[str]]]:
        """
        Detect duplicate and cross-posted messages.

        Args:
            messages: List of unified messages to check

        Returns:
            Tuple of (unique_messages, duplicate_groups)
            - unique_messages: Messages with duplicates removed
            - duplicate_groups: Groups of message IDs that are duplicates
        """
        # Group by content hash
        content_groups: Dict[str, List[UnifiedMessage]] = {}

        for msg in messages:
            # Create content hash (excluding timestamp and platform)
            content_hash = hashlib.md5(
                msg.content.lower().strip().encode()
            ).hexdigest()

            if content_hash not in content_groups:
                content_groups[content_hash] = []
            content_groups[content_hash].append(msg)

        # Find duplicates
        unique_messages = []
        duplicate_groups = {}

        for content_hash, msg_group in content_groups.items():
            if len(msg_group) > 1:
                # Multiple messages with same content = duplicates/cross-posts
                # Take the earliest one as the original
                msg_group.sort(key=lambda m: m.timestamp)
                original = msg_group[0]
                duplicates = msg_group[1:]

                original.is_cross_posted = True
                original.related_message_ids = [d.id for d in duplicates]

                for dup in duplicates:
                    dup.is_duplicate = True
                    dup.related_message_ids = [original.id]

                unique_messages.append(original)
                duplicate_groups[original.id] = [d.id for d in duplicates]

                # Track cross-platform mapping
                if len(set(m.platform for m in msg_group)) > 1:
                    # Cross-platform duplicate
                    unified_id = original.unified_id
                    self.cross_platform_map[unified_id] = [m.platform_message_id for m in msg_group]
            else:
                unique_messages.append(msg_group[0])

        return unique_messages, duplicate_groups

    def create_conversation_threads(self, messages: List[UnifiedMessage]) -> Dict[str, List[str]]:
        """
        Create conversation threads across platforms.

        Groups messages by conversation_id or thread_id.

        Args:
            messages: List of unified messages

        Returns:
            Dictionary mapping conversation_id -> [message_ids]
        """
        threads: Dict[str, List[str]] = {}

        for msg in messages:
            # Use conversation_id if available, otherwise thread_id
            conv_id = msg.conversation_id or msg.thread_id

            if not conv_id:
                # Generate temporary conversation ID
                conv_id = f"{msg.platform}_{msg.channel_id}_conversation"

            if conv_id not in threads:
                threads[conv_id] = []

            threads[conv_id].append(msg.id)

            # Update message with conversation ID
            if not msg.conversation_id:
                msg.conversation_id = conv_id

        # Sort messages in each thread by timestamp
        for conv_id in threads:
            threads[conv_id].sort(key=lambda mid: (
                self.processed_messages[mid].timestamp if mid in self.processed_messages else datetime.min
            ))

        self.conversation_threads = threads
        return threads

    def process_messages(self, raw_messages: List[Dict[str, Any]]) -> List[UnifiedMessage]:
        """
        Process a batch of raw messages from any platform(s).

        This is the main entry point for unified message processing.

        Args:
            raw_messages: List of raw messages from platforms

        Returns:
            List of processed UnifiedMessage objects
        """
        logger.info(f"Processing {len(raw_messages)} raw messages")

        # Step 1: Normalize all messages
        unified_messages = []
        for raw_msg in raw_messages:
            try:
                unified = self.normalize_message(raw_msg)
                unified_messages.append(unified)

                # Store in processed messages
                self.processed_messages[unified.id] = unified
                self.message_hashes.add(unified.unified_id)

            except Exception as e:
                logger.error(f"Error normalizing message {raw_msg.get('id')}: {e}")
                continue

        logger.info(f"Normalized {len(unified_messages)} messages")

        # Step 2: Detect duplicates and cross-posts
        unique_messages, duplicate_groups = self.detect_duplicates(unified_messages)
        logger.info(f"Found {len(unique_messages)} unique messages, {len(duplicate_groups)} duplicate groups")

        # Step 3: Create conversation threads
        threads = self.create_conversation_threads(unique_messages)
        logger.info(f"Created {len(threads)} conversation threads")

        # Step 4: Mark as processed
        for msg in unique_messages:
            msg.is_processed = True

        return unique_messages

    def get_conversation_history(self, conversation_id: str, limit: int = 50) -> List[UnifiedMessage]:
        """
        Get message history for a conversation.

        Args:
            conversation_id: Conversation ID
            limit: Maximum number of messages to return

        Returns:
            List of messages in chronological order
        """
        if conversation_id not in self.conversation_threads:
            return []

        message_ids = self.conversation_threads[conversation_id][:limit]
        messages = [
            self.processed_messages[mid]
            for mid in message_ids
            if mid in self.processed_messages
        ]

        return messages

    def search_messages(
        self,
        query: str,
        platforms: Optional[List[str]] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        limit: int = 100
    ) -> List[UnifiedMessage]:
        """
        Search processed messages.

        Args:
            query: Search query (searches in content, subject, sender)
            platforms: Filter by platforms
            start_date: Filter by start date
            end_date: Filter by end date
            limit: Maximum results

        Returns:
            List of matching messages
        """
        results = []
        query_lower = query.lower()

        for msg in self.processed_messages.values():
            # Platform filter
            if platforms and msg.platform not in platforms:
                continue

            # Date filter
            if start_date and msg.timestamp < start_date:
                continue
            if end_date and msg.timestamp > end_date:
                continue

            # Skip duplicates
            if msg.is_duplicate:
                continue

            # Search in content, subject, sender
            searchable_text = f"{msg.content} {msg.subject or ''} {msg.sender_name}".lower()
            if query_lower in searchable_text:
                results.append(msg)

                if len(results) >= limit:
                    break

        # Sort by timestamp (most recent first)
        results.sort(key=lambda m: m.timestamp, reverse=True)

        return results

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about processed messages.

        Returns:
            Dictionary with message statistics
        """
        total_messages = len(self.processed_messages)
        unique_messages = sum(1 for m in self.processed_messages.values() if not m.is_duplicate)
        duplicate_messages = total_messages - unique_messages

        # Count by platform
        platform_counts: Dict[str, int] = {}
        for msg in self.processed_messages.values():
            platform_counts[msg.platform] = platform_counts.get(msg.platform, 0) + 1

        # Count by type
        type_counts: Dict[str, int] = {}
        for msg in self.processed_messages.values():
            type_counts[msg.message_type] = type_counts.get(msg.message_type, 0) + 1

        return {
            "total_messages": total_messages,
            "unique_messages": unique_messages,
            "duplicate_messages": duplicate_messages,
            "duplicate_rate": f"{(duplicate_messages / total_messages * 100):.1f}%" if total_messages > 0 else "0%",
            "platforms": platform_counts,
            "message_types": type_counts,
            "conversations": len(self.conversation_threads),
            "cross_platform_posts": sum(1 for m in self.processed_messages.values() if m.is_cross_posted)
        }


# Singleton instance
unified_processor = UnifiedMessageProcessor()


def get_unified_processor() -> UnifiedMessageProcessor:
    """Get the singleton unified message processor"""
    return unified_processor
