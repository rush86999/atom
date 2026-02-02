"""
Cross-Platform Correlation Engine
Detects and links conversations across multiple communication platforms.
"""

import logging
from typing import Dict, Any, List, Optional, Set, Tuple
from datetime import datetime, timedelta, timezone
from collections import defaultdict
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class CorrelationStrength(Enum):
    """Strength of correlation between conversations"""
    STRONG = "strong"      # Same participants, similar topic, close timing
    MODERATE = "moderate"  # Some matching attributes
    WEAK = "weak"          # Minimal evidence of connection


@dataclass
class LinkedConversation:
    """A conversation linked across platforms"""
    conversation_id: str
    threads: Dict[str, str]  # platform -> thread_id
    platforms: Set[str]
    participants: Set[str]
    participant_emails: Set[str] = field(default_factory=set)
    message_count: int = 0
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None
    correlation_strength: CorrelationStrength = CorrelationStrength.MODERATE
    topic_keywords: Set[str] = field(default_factory=set)
    unified_messages: List[Dict[str, Any]] = field(default_factory=list)


@dataclass
class CrossPlatformLink:
    """A link between two threads on different platforms"""
    source_platform: str
    source_thread: str
    target_platform: str
    target_thread: str
    strength: CorrelationStrength
    reason: str  # Why they were linked
    shared_participants: Set[str] = field(default_factory=set)
    temporal_distance: Optional[float] = None  # Time difference in seconds


class CrossPlatformCorrelationEngine:
    """
    Engine for detecting and correlating conversations across platforms.

    Features:
    - Participant-based linking (same users across platforms)
    - Temporal correlation (overlapping time periods)
    - Content similarity (shared topics, keywords)
    - Cross-references (mentions of other platforms)
    - Unified conversation timeline
    """

    # Email patterns for extracting user identity
    EMAIL_PATTERNS = {
        "slack": r"<mailto:(?P<email>[^|]+)\|[^>]+>",
        "teams": r"<(?P<email>[^@]+@[^>]+)>",
        "gmail": r"<(?P<email>[^@]+@[^>]+)>"
    }

    def __init__(self, similarity_threshold: float = 0.3):
        """
        Initialize the correlation engine.

        Args:
            similarity_threshold: Minimum similarity score for content correlation (0-1)
        """
        self.similarity_threshold = similarity_threshold
        self.linked_conversations: Dict[str, LinkedConversation] = {}
        self.cross_platform_links: List[CrossPlatformLink] = []

    def correlate_conversations(
        self,
        messages: List[Dict[str, Any]]
    ) -> List[LinkedConversation]:
        """
        Correlate conversations across platforms.

        Args:
            messages: List of unified messages from multiple platforms

        Returns:
            List of linked conversations
        """
        # Group messages by thread
        thread_messages = self._group_by_thread(messages)

        # Extract thread metadata
        thread_metadata = self._extract_thread_metadata(thread_messages)

        # Find correlations using multiple strategies
        correlations = []

        # Strategy 1: Participant-based correlation
        correlations.extend(self._correlate_by_participants(thread_metadata))

        # Strategy 2: Temporal correlation (overlapping time periods)
        correlations.extend(self._correlate_by_time(thread_metadata))

        # Strategy 3: Content similarity
        correlations.extend(self._correlate_by_content(thread_metadata))

        # Strategy 4: Cross-references
        correlations.extend(self._correlate_by_references(thread_metadata))

        # Merge overlapping correlations
        merged = self._merge_correlations(correlations, thread_messages)

        # Build unified conversation timelines
        for conv in merged:
            conv.unified_messages = self._build_unified_timeline(
                conv.threads, thread_messages
            )

        self.linked_conversations = {c.conversation_id: c for c in merged}
        return merged

    def _group_by_thread(
        self,
        messages: List[Dict[str, Any]]
    ) -> Dict[Tuple[str, str], List[Dict[str, Any]]]:
        """Group messages by (platform, thread_id)"""
        grouped = defaultdict(list)
        for msg in messages:
            platform = msg.get("platform", "unknown")
            thread_id = msg.get("thread_id") or msg.get("conversation_id") or "no_thread"

            # Store with original timestamp for sorting
            grouped[(platform, thread_id)].append(msg)

        return dict(grouped)

    def _extract_thread_metadata(
        self,
        thread_messages: Dict[Tuple[str, str], List[Dict[str, Any]]]
    ) -> Dict[Tuple[str, str], Dict[str, Any]]:
        """Extract metadata for each thread"""
        metadata = {}

        for (platform, thread_id), messages in thread_messages.items():
            if not messages:
                continue

            # Parse timestamps
            timestamps = []
            for msg in messages:
                ts = self._parse_timestamp(msg.get("timestamp"))
                if ts:
                    timestamps.append(ts)

            # Extract participants
            participants = set()
            participant_emails = set()
            for msg in messages:
                sender = msg.get("sender_name") or msg.get("sender")
                if sender:
                    participants.add(sender)

                sender_email = msg.get("sender_email")
                if sender_email:
                    participant_emails.add(sender_email)

                # Extract mentions
                mentions = msg.get("mentions", [])
                participants.update(mentions)

            # Extract topics/keywords from content
            keywords = self._extract_keywords(messages)

            # Get thread ID for display
            display_thread_id = thread_id if thread_id != "no_thread" else messages[0].get("id", "unknown")

            metadata[(platform, thread_id)] = {
                "platform": platform,
                "thread_id": display_thread_id,
                "message_count": len(messages),
                "participants": participants,
                "participant_emails": participant_emails,
                "start_time": min(timestamps) if timestamps else None,
                "end_time": max(timestamps) if timestamps else None,
                "keywords": keywords,
                "messages": messages
            }

        return metadata

    def _correlate_by_participants(
        self,
        thread_metadata: Dict[Tuple[str, str], Dict[str, Any]]
    ) -> List[LinkedConversation]:
        """Correlate threads based on shared participants"""
        conversations = []
        processed = set()

        for (plat1, thread1), meta1 in thread_metadata.items():
            if (plat1, thread1) in processed:
                continue

            # Find related threads
            related_threads = {(plat1, thread1)}
            all_participants = meta1["participants"].copy()
            all_emails = meta1["participant_emails"].copy()

            for (plat2, thread2), meta2 in thread_metadata.items():
                if (plat2, thread2) in processed or (plat2, thread2) == (plat1, thread1):
                    continue

                # Check for shared participants
                shared_names = meta1["participants"] & meta2["participants"]
                shared_emails = meta1["participant_emails"] & meta2["participant_emails"]

                # Check for email-name cross-matches
                for email in meta1["participant_emails"]:
                    username = email.split("@")[0].lower()
                    if any(username in p.lower() for p in meta2["participants"]):
                        shared_emails.add(email)

                for email in meta2["participant_emails"]:
                    username = email.split("@")[0].lower()
                    if any(username in p.lower() for p in meta1["participants"]):
                        shared_emails.add(email)

                if shared_names or shared_emails:
                    related_threads.add((plat2, thread2))
                    all_participants.update(meta2["participants"])
                    all_emails.update(meta2["participant_emails"])

                    # Create cross-platform link
                    strength = CorrelationStrength.STRONG if len(shared_names) >= 2 else CorrelationStrength.MODERATE
                    link = CrossPlatformLink(
                        source_platform=plat1,
                        source_thread=thread1,
                        target_platform=plat2,
                        target_thread=thread2,
                        strength=strength,
                        reason=f"Shared {len(shared_names)} participants, {len(shared_emails)} emails",
                        shared_participants=shared_names | shared_emails
                    )
                    self.cross_platform_links.append(link)

            if len(related_threads) > 1:
                # Create linked conversation
                all_keywords = set()
                for (p, t) in related_threads:
                    all_keywords.update(thread_metadata[(p, t)]["keywords"])

                conv = LinkedConversation(
                    conversation_id=f"conv_{len(conversations)}",
                    threads={p: t for (p, t) in related_threads},
                    platforms={p for (p, _) in related_threads},
                    participants=all_participants,
                    participant_emails=all_emails,
                    message_count=sum(m["message_count"] for (p, t), m in thread_metadata.items() if (p, t) in related_threads),
                    start_time=min(m["start_time"] for (p, t), m in thread_metadata.items() if (p, t) in related_threads if m["start_time"]),
                    end_time=max(m["end_time"] for (p, t), m in thread_metadata.items() if (p, t) in related_threads if m["end_time"]),
                    correlation_strength=CorrelationStrength.STRONG if len(related_threads) >= 3 else CorrelationStrength.MODERATE,
                    topic_keywords=all_keywords
                )
                conversations.append(conv)
                processed.update(related_threads)

        return conversations

    def _correlate_by_time(
        self,
        thread_metadata: Dict[Tuple[str, str], Dict[str, Any]]
    ) -> List[LinkedConversation]:
        """Correlate threads based on overlapping time periods"""
        conversations = []
        processed = set()

        for (plat1, thread1), meta1 in thread_metadata.items():
            if (plat1, thread1) in processed or not meta1["start_time"] or not meta1["end_time"]:
                continue

            related_threads = {(plat1, thread1)}
            window_start = meta1["start_time"]
            window_end = meta1["end_time"] + timedelta(hours=2)  # 2-hour window

            for (plat2, thread2), meta2 in thread_metadata.items():
                if (plat2, thread2) in processed or (plat2, thread2) == (plat1, thread1):
                    continue

                if not meta2["start_time"] or not meta2["end_time"]:
                    continue

                # Check for time overlap
                if meta2["start_time"] <= window_end and meta2["end_time"] >= window_start:
                    related_threads.add((plat2, thread2))

                    # Create cross-platform link
                    time_diff = abs((meta1["start_time"] - meta2["start_time"]).total_seconds())
                    link = CrossPlatformLink(
                        source_platform=plat1,
                        source_thread=thread1,
                        target_platform=plat2,
                        target_thread=thread2,
                        strength=CorrelationStrength.WEAK,
                        reason=f"Temporal proximity ({time_diff/60:.0f} minutes apart)",
                        temporal_distance=time_diff
                    )
                    self.cross_platform_links.append(link)

            if len(related_threads) > 1:
                all_keywords = set()
                for (p, t) in related_threads:
                    all_keywords.update(thread_metadata[(p, t)]["keywords"])

                conv = LinkedConversation(
                    conversation_id=f"conv_time_{len(conversations)}",
                    threads={p: t for (p, t) in related_threads},
                    platforms={p for (p, _) in related_threads},
                    participants=set().union(*[thread_metadata[(p, t)]["participants"] for (p, t) in related_threads]),
                    participant_emails=set().union(*[thread_metadata[(p, t)]["participant_emails"] for (p, t) in related_threads]),
                    message_count=sum(m["message_count"] for (p, t), m in thread_metadata.items() if (p, t) in related_threads),
                    start_time=min(m["start_time"] for (p, t), m in thread_metadata.items() if (p, t) in related_threads if m["start_time"]),
                    end_time=max(m["end_time"] for (p, t), m in thread_metadata.items() if (p, t) in related_threads if m["end_time"]),
                    correlation_strength=CorrelationStrength.WEAK,
                    topic_keywords=all_keywords
                )
                conversations.append(conv)
                processed.update(related_threads)

        return conversations

    def _correlate_by_content(
        self,
        thread_metadata: Dict[Tuple[str, str], Dict[str, Any]]
    ) -> List[LinkedConversation]:
        """Correlate threads based on content similarity"""
        conversations = []
        processed = set()

        for (plat1, thread1), meta1 in thread_metadata.items():
            if (plat1, thread1) in processed or plat1 == "unknown":
                continue

            keywords1 = meta1["keywords"]
            if not keywords1:
                continue

            related_threads = {(plat1, thread1)}
            all_keywords = keywords1.copy()

            for (plat2, thread2), meta2 in thread_metadata.items():
                if (plat2, thread2) in processed or (plat2, thread2) == (plat1, thread1) or plat2 == "unknown":
                    continue

                keywords2 = meta2["keywords"]
                if not keywords2:
                    continue

                # Calculate keyword overlap
                overlap = keywords1 & keywords2
                total_keywords = keywords1 | keywords2

                if total_keywords:
                    similarity = len(overlap) / len(total_keywords)

                    if similarity >= self.similarity_threshold:
                        related_threads.add((plat2, thread2))
                        all_keywords.update(keywords2)

                        # Create cross-platform link
                        strength = CorrelationStrength.MODERATE if similarity > 0.5 else CorrelationStrength.WEAK
                        link = CrossPlatformLink(
                            source_platform=plat1,
                            source_thread=thread1,
                            target_platform=plat2,
                            target_thread=thread2,
                            strength=strength,
                            reason=f"Content similarity ({similarity:.1%})"
                        )
                        self.cross_platform_links.append(link)

            if len(related_threads) > 1:
                conv = LinkedConversation(
                    conversation_id=f"conv_content_{len(conversations)}",
                    threads={p: t for (p, t) in related_threads},
                    platforms={p for (p, _) in related_threads},
                    participants=set().union(*[thread_metadata[(p, t)]["participants"] for (p, t) in related_threads]),
                    topic_keywords=all_keywords,
                    correlation_strength=CorrelationStrength.WEAK
                )
                conversations.append(conv)
                processed.update(related_threads)

        return conversations

    def _correlate_by_references(
        self,
        thread_metadata: Dict[Tuple[str, str], Dict[str, Any]]
    ) -> List[LinkedConversation]:
        """Correlate threads based on cross-references to other platforms"""
        conversations = []

        for (platform, thread_id), meta in thread_metadata.items():
            for msg in meta["messages"]:
                content = msg.get("content", "").lower()

                # Check for mentions of other platforms
                platform_references = {
                    "slack": ["slack", "#", "channel"],
                    "teams": ["teams", "microsoft", "meeting"],
                    "gmail": ["email", "mail", "thread"],
                    "outlook": ["outlook", "email"]
                }

                for ref_platform, keywords in platform_references.items():
                    if ref_platform == platform:
                        continue

                    if any(kw in content for kw in keywords):
                        # Found a reference - try to find matching thread
                        for (target_plat, target_thread), target_meta in thread_metadata.items():
                            if target_plat == ref_platform:
                                # Check if time is close
                                if meta["start_time"] and target_meta["start_time"]:
                                    time_diff = abs((meta["start_time"] - target_meta["start_time"]).total_seconds())
                                    if time_diff < 3600:  # Within 1 hour
                                        conv = LinkedConversation(
                                            conversation_id=f"conv_ref_{len(conversations)}",
                                            threads={platform: thread_id, ref_platform: target_thread},
                                            platforms={platform, ref_platform},
                                            participants=meta["participants"] | target_meta["participants"],
                                            correlation_strength=CorrelationStrength.MODERATE
                                        )
                                        conversations.append(conv)

        return conversations

    def _merge_correlations(
        self,
        correlations: List[LinkedConversation],
        thread_messages: Dict[Tuple[str, str], List[Dict[str, Any]]]
    ) -> List[LinkedConversation]:
        """Merge overlapping correlations"""
        if not correlations:
            return []

        # Group by thread overlap
        merged = []
        used = set()

        for i, conv1 in enumerate(correlations):
            if i in used:
                continue

            merged_threads = conv1.threads.copy()
            merged_platforms = conv1.platforms.copy()
            merged_participants = conv1.participants.copy()
            merged_keywords = conv1.topic_keywords.copy()

            for j, conv2 in enumerate(correlations[i+1:], i+1):
                if j in used:
                    continue

                # Check for overlap
                if conv1.threads.items() & conv2.threads.items():
                    merged_threads.update(conv2.threads)
                    merged_platforms.update(conv2.platforms)
                    merged_participants.update(conv2.participants)
                    merged_keywords.update(conv2.topic_keywords)
                    used.add(j)

            # Create merged conversation
            merged_conv = LinkedConversation(
                conversation_id=f"conv_merged_{len(merged)}",
                threads=merged_threads,
                platforms=merged_platforms,
                participants=merged_participants,
                participant_emails=set().union(*[
                    thread_messages[(p, t)][0].get("participant_emails", set()) if (p, t) in thread_messages else set()
                    for p, t in merged_threads.items()
                ]),
                message_count=sum(
                    thread_messages[(p, t)][0].get("message_count", 0) if (p, t) in thread_messages else 0
                    for p, t in merged_threads.items()
                ),
                correlation_strength=CorrelationStrength.STRONG if len(merged_platforms) > 2 else CorrelationStrength.MODERATE,
                topic_keywords=merged_keywords
            )
            merged.append(merged_conv)
            used.add(i)

        return merged

    def _build_unified_timeline(
        self,
        threads: Dict[str, str],
        thread_messages: Dict[Tuple[str, str], List[Dict[str, Any]]]
    ) -> List[Dict[str, Any]]:
        """Build unified message timeline from multiple threads"""
        all_messages = []

        for platform, thread_id in threads.items():
            if (platform, thread_id) in thread_messages:
                messages = thread_messages[(platform, thread_id)]
                for msg in messages:
                    # Add platform context
                    msg_copy = msg.copy()
                    msg_copy["_correlation_source"] = platform
                    msg_copy["_correlation_thread"] = thread_id
                    all_messages.append(msg_copy)

        # Sort by timestamp
        all_messages.sort(key=lambda m: self._parse_timestamp(m.get("timestamp")) or datetime.min)

        return all_messages

    def get_unified_timeline(
        self,
        conversation_id: str
    ) -> Optional[List[Dict[str, Any]]]:
        """Get unified timeline for a conversation"""
        if conversation_id in self.linked_conversations:
            return self.linked_conversations[conversation_id].unified_messages
        return None

    def _extract_keywords(self, messages: List[Dict[str, Any]]) -> Set[str]:
        """Extract keywords from messages"""
        import re

        keywords = set()
        important_words = {
            "urgent", "deadline", "meeting", "review", "approval",
            "deploy", "release", "bug", "issue", "feature",
            "project", "task", "milestone", "blocked", "blocked"
        }

        for msg in messages:
            content = msg.get("content", "").lower()
            words = re.findall(r'\b\w+\b', content)

            # Filter for meaningful words (3+ chars)
            for word in words:
                if len(word) >= 3 and word in important_words:
                    keywords.add(word)

        return keywords

    def _parse_timestamp(self, timestamp: Any) -> Optional[datetime]:
        """Parse timestamp to datetime"""
        if timestamp is None:
            return None

        if isinstance(timestamp, datetime):
            return timestamp

        if isinstance(timestamp, str):
            try:
                return datetime.fromisoformat(timestamp)
            except (ValueError, TypeError):
                return None

        return None


# Singleton instance
correlation_engine = CrossPlatformCorrelationEngine()


def get_cross_platform_correlation_engine() -> CrossPlatformCorrelationEngine:
    """Get the singleton cross-platform correlation engine"""
    return correlation_engine
