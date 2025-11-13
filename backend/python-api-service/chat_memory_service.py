"""
Chat Memory Service for ATOM Backend

This service provides integration between the chat interface and LanceDB memory system,
implementing short-term and long-term memory for conversations with human-brain-like memory patterns.
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional, Any
import logging

# Try to import LanceDB components
try:
    from lancedb_handler import (
        store_conversation_context,
        search_conversation_context,
        get_conversation_history,
        get_lancedb_connection,
        create_generic_document_tables_if_not_exist
    )
    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB handler not available, memory features will be limited")

logger = logging.getLogger(__name__)


class ConversationMemory:
    """Represents a conversation memory entry"""

    def __init__(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
        memory_id: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        self.id = memory_id or str(uuid.uuid4())
        self.user_id = user_id
        self.session_id = session_id
        self.role = role  # 'user', 'assistant', 'system'
        self.content = content
        self.message_type = message_type
        self.metadata = metadata or {}
        self.timestamp = timestamp or datetime.now(timezone.utc)
        self.embedding = None
        self.importance_score = self._calculate_importance()

    def _calculate_importance(self) -> float:
        """Calculate importance score for memory retention decisions"""
        importance = 0.5  # Base importance

        # Boost importance for workflow-related content
        if self.metadata.get('workflow_id'):
            importance += 0.3

        # Boost for user questions and commands
        if self.role == 'user':
            if '?' in self.content or any(keyword in self.content.lower() for keyword in ['how to', 'can you', 'please', 'help']):
                importance += 0.2

        # Boost for assistant responses with actions
        if self.role == 'assistant' and any(keyword in self.content.lower() for keyword in ['created', 'scheduled', 'automated', 'set up']):
            importance += 0.2

        # Content length factor
        if len(self.content) > 200:
            importance += 0.1

        return min(importance, 1.0)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for storage"""
        return {
            'id': self.id,
            'user_id': self.user_id,
            'session_id': self.session_id,
            'role': self.role,
            'content': self.content,
            'message_type': self.message_type,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'importance_score': self.importance_score
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ConversationMemory':
        """Create from dictionary"""
        memory = cls(
            user_id=data['user_id'],
            session_id=data['session_id'],
            role=data['role'],
            content=data['content'],
            message_type=data.get('message_type', 'text'),
            metadata=data.get('metadata', {}),
            memory_id=data['id'],
            timestamp=datetime.fromisoformat(data['timestamp'])
        )
        memory.importance_score = data.get('importance_score', 0.5)
        return memory


class MemoryContext:
    """Represents memory context for chat responses"""

    def __init__(
        self,
        short_term_memories: List[ConversationMemory],
        long_term_memories: List[ConversationMemory],
        user_patterns: List[Dict[str, Any]],
        conversation_summary: str,
        relevance_score: float
    ):
        self.short_term_memories = short_term_memories
        self.long_term_memories = long_term_memories
        self.user_patterns = user_patterns
        self.conversation_summary = conversation_summary
        self.relevance_score = relevance_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'short_term_memories': [m.to_dict() for m in self.short_term_memories],
            'long_term_memories': [m.to_dict() for m in self.long_term_memories],
            'user_patterns': self.user_patterns,
            'conversation_summary': self.conversation_summary,
            'relevance_score': self.relevance_score
        }


class ChatMemoryService:
    """
    Service for managing chat memory with short-term and long-term storage

    Features:
    - Short-term memory (in-memory, session-based)
    - Long-term memory (LanceDB vector storage)
    - User pattern recognition
    - Context-aware memory retrieval
    - Memory importance scoring
    """

    def __init__(self):
        self.short_term_memory: Dict[str, List[ConversationMemory]] = {}  # session_id -> memories
        self.user_patterns: Dict[str, List[Dict[str, Any]]] = {}  # user_id -> patterns
        self.memory_access_counts: Dict[str, int] = {}  # memory_id -> access count
        self.session_timeouts: Dict[str, asyncio.Task] = {}  # session_id -> cleanup task

        # Configuration
        self.short_term_memory_size = 50
        self.long_term_threshold = 0.7
        self.similarity_threshold = 0.6
        self.session_timeout_minutes = 60

        logger.info("ChatMemoryService initialized")

    async def store_conversation(self, memory: ConversationMemory) -> Dict[str, Any]:
        """
        Store conversation in both short-term and long-term memory

        Args:
            memory: Conversation memory to store

        Returns:
            Storage result with status and memory ID
        """
        try:
            # Store in short-term memory
            await self._store_short_term_memory(memory)

            # Store in long-term memory if important enough
            if memory.importance_score >= self.long_term_threshold:
                await self._store_long_term_memory(memory)

            # Update user patterns
            await self._update_user_patterns(memory)

            logger.info(f"Stored conversation memory for user {memory.user_id}")

            return {
                'status': 'success',
                'memory_id': memory.id,
                'stored_in_short_term': True,
                'stored_in_long_term': memory.importance_score >= self.long_term_threshold,
                'importance_score': memory.importance_score
            }

        except Exception as e:
            logger.error(f"Failed to store conversation memory: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    async def get_memory_context(
        self,
        user_id: str,
        session_id: str,
        current_message: str,
        context_window: int = 10
    ) -> MemoryContext:
        """
        Get relevant memory context for chat response generation

        Args:
            user_id: User identifier
            session_id: Session identifier
            current_message: Current user message
            context_window: Number of memories to consider

        Returns:
            Memory context with relevant memories
        """
        try:
            # Get short-term memories from current session
            short_term_memories = await self._get_short_term_memories(session_id, context_window)

            # Search long-term memories using semantic similarity
            long_term_memories = await self._search_long_term_memories(user_id, current_message)

            # Get relevant user patterns
            user_patterns = await self._get_relevant_patterns(user_id, current_message)

            # Combine and rank memories
            all_memories = self._combine_and_rank_memories(
                short_term_memories, long_term_memories, user_patterns
            )

            # Generate context summary
            context_summary = self._generate_context_summary(all_memories, current_message)

            # Calculate relevance score
            relevance_score = self._calculate_relevance_score(all_memories, current_message)

            # Update access counts
            for memory in all_memories[:context_window]:
                self._increment_access_count(memory.id)

            return MemoryContext(
                short_term_memories=short_term_memories[:5],
                long_term_memories=long_term_memories[:5],
                user_patterns=user_patterns[:3],
                conversation_summary=context_summary,
                relevance_score=relevance_score
            )

        except Exception as e:
            logger.error(f"Failed to get memory context: {e}")
            # Return empty context on error
            return MemoryContext([], [], [], "Memory context unavailable", 0.0)

    async def get_conversation_history(
        self,
        user_id: str,
        session_id: Optional[str] = None,
        limit: int = 50
    ) -> List[ConversationMemory]:
        """
        Get conversation history for user/session

        Args:
            user_id: User identifier
            session_id: Optional session identifier
            limit: Maximum number of memories to return

        Returns:
            List of conversation memories
        """
        try:
            memories = []

            # Get from short-term memory
            if session_id and session_id in self.short_term_memory:
                session_memories = self.short_term_memory[session_id]
                memories.extend([m for m in session_memories if m.user_id == user_id])

            # Get from long-term memory if LanceDB available
            if LANCEDB_AVAILABLE:
                try:
                    db_conn = await get_lancedb_connection()
                    if db_conn:
                        history_result = await get_conversation_history(
                            db_conn, user_id, session_id, limit
                        )
                        if history_result.get('status') == 'success':
                            for memory_data in history_result.get('data', []):
                                try:
                                    memory = ConversationMemory.from_dict(memory_data)
                                    memories.append(memory)
                                except Exception as e:
                                    logger.warning(f"Failed to parse memory data: {e}")
                except Exception as e:
                    logger.warning(f"Failed to get long-term history: {e}")

            # Sort by timestamp and limit
            memories.sort(key=lambda m: m.timestamp, reverse=True)
            return memories[:limit]

        except Exception as e:
            logger.error(f"Failed to get conversation history: {e}")
            return []

    async def clear_session_memory(self, session_id: str) -> Dict[str, Any]:
        """
        Clear short-term memory for a session

        Args:
            session_id: Session identifier to clear

        Returns:
            Clear operation result
        """
        try:
            if session_id in self.short_term_memory:
                del self.short_term_memory[session_id]

            # Cancel any pending timeout task
            if session_id in self.session_timeouts:
                self.session_timeouts[session_id].cancel()
                del self.session_timeouts[session_id]

            logger.info(f"Cleared short-term memory for session: {session_id}")

            return {
                'status': 'success',
                'message': f'Memory cleared for session {session_id}'
            }

        except Exception as e:
            logger.error(f"Failed to clear session memory: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    def get_memory_stats(self, user_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get memory statistics

        Args:
            user_id: Optional user identifier for user-specific stats

        Returns:
            Memory statistics
        """
        try:
            # Calculate counts
            if user_id:
                short_term_count = sum(
                    len([m for m in memories if m.user_id == user_id])
                    for memories in self.short_term_memory.values()
                )
                pattern_count = len(self.user_patterns.get(user_id, []))
            else:
                short_term_count = sum(len(memories) for memories in self.short_term_memory.values())
                pattern_count = sum(len(patterns) for patterns in self.user_patterns.values())

            total_accesses = sum(self.memory_access_counts.values())

            return {
                'status': 'success',
                'short_term_memory_count': short_term_count,
                'user_pattern_count': pattern_count,
                'active_sessions': len(self.short_term_memory),
                'total_memory_accesses': total_accesses,
                'lancedb_available': LANCEDB_AVAILABLE
            }

        except Exception as e:
            logger.error(f"Failed to get memory stats: {e}")
            return {
                'status': 'error',
                'message': str(e)
            }

    # Private methods

    async def _store_short_term_memory(self, memory: ConversationMemory):
        """Store memory in short-term storage"""
        if memory.session_id not in self.short_term_memory:
            self.short_term_memory[memory.session_id] = []
            # Start session timeout
            self._start_session_timeout(memory.session_id)

        session_memories = self.short_term_memory[memory.session_id]
        session_memories.append(memory)

        # Enforce size limit
        if len(session_memories) > self.short_term_memory_size:
            session_memories.pop(0)

    async def _store_long_term_memory(self, memory: ConversationMemory):
        """Store memory in LanceDB long-term storage"""
        if not LANCEDB_AVAILABLE:
            return

        try:
            db_conn = await get_lancedb_connection()
            if not db_conn:
                return

            # Prepare data for storage
            memory_data = memory.to_dict()

            # Generate simple embedding (in production, use proper embedding service)
            embedding = self._generate_simple_embedding(memory.content)

            # Store in LanceDB
            result = await store_conversation_context(db_conn, memory_data, embedding)

            if result.get('status') == 'success':
                logger.debug(f"Stored memory in long-term storage: {memory.id}")
            else:
                logger.warning(f"Failed to store in long-term storage: {result.get('message')}")

        except Exception as e:
            logger.warning(f"Long-term storage failed: {e}")

    async def _get_short_term_memories(self, session_id: str, limit: int) -> List[ConversationMemory]:
        """Get short-term memories for session"""
        if session_id not in self.short_term_memory:
            return []

        return self.short_term_memory[session_id][-limit:]

    async def _search_long_term_memories(self, user_id: str, query: str) -> List[ConversationMemory]:
        """Search long-term memories using semantic similarity"""
        if not LANCEDB_AVAILABLE:
            return []

        try:
            db_conn = await get_lancedb_connection()
            if not db_conn:
                return []

            # Generate embedding for query
            query_embedding = self._generate_simple_embedding(query)

            # Search LanceDB
            search_result = await search_conversation_context(
                db_conn=db_conn,
                query_embedding=query_embedding,
                user_id=user_id,
                limit=10,
                similarity_threshold=self.similarity_threshold
            )

            if search_result.get('status') == 'success':
                memories = []
                for memory_data in search_result.get('data', []):
                    try:
                        memory = ConversationMemory.from_dict(memory_data)
                        memories.append(memory)
                    except Exception as e:
                        logger.warning(f"Failed to parse search result: {e}")
                return memories

            return []

        except Exception as e:
            logger.warning(f"Long-term search failed: {e}")
            return []

    async def _update_user_patterns(self, memory: ConversationMemory):
        """Update user patterns based on new memory"""
        if memory.user_id not in self.user_patterns:
            self.user_patterns[memory.user_id] = []

        patterns = self.user_patterns[memory.user_id]

        # Detect workflow patterns
        if memory.metadata.get('workflow_id'):
            workflow_pattern = next(
                (p for p in patterns if p.get('type') == 'workflow' and
                 p.get('workflow_id') == memory.metadata['workflow_id']),
                None
            )

            if workflow_pattern:
                workflow_pattern['frequency'] += 1
                workflow_pattern['last_observed'] = datetime.now(timezone.utc).isoformat()
                workflow_pattern['confidence'] = min(1.0, workflow_pattern.get('confidence', 0.5) + 0.1)
            else:
                patterns.append({
                    'type': 'workflow',
                    'workflow_id': memory.metadata['workflow_id'],
                    'frequency': 1,
                    'confidence': 0.5,
                    'last_observed': datetime.now(timezone_utc).isoformat()
                })

    async def _get_relevant_patterns(self, user_id: str, current_message: str) -> List[Dict[str, Any]]:
        """Get relevant user patterns for current context"""
        if user_id not in self.user_patterns:
            return []

        patterns = self.user_patterns[user_id]

        # Filter by recency and confidence
        one_week_ago = datetime.now(timezone.utc).timestamp() - (7 * 24 * 60 * 60)
        relevant_patterns = [
            p for p in patterns
            if datetime.fromisoformat(p['last_observed']).timestamp() > one_week_ago
            and p.get('confidence', 0) > 0.3
        ]

        return sorted(relevant_patterns, key=lambda p: p.get('confidence', 0), reverse=True)[:5]

    def _combine_and_rank_memories(
        self,
        short_term: List[ConversationMemory],
        long_term: List[ConversationMemory],
        patterns: List[Dict[str, Any]]
    ) -> List[ConversationMemory]:
        """Combine and rank memories by relevance"""
        all_memories = short_term + long_term

        # Score each memory
        scored_memories = []
        for memory in all
