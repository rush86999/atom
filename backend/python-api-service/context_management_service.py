import logging
import json
from typing import Dict, List, Any, Optional
from datetime import datetime

# Try to import LanceDB for semantic conversation retrieval
try:
    from lancedb_handler import (
        store_conversation_context,
        search_conversation_context,
        get_conversation_history as get_lancedb_conversation_history,
        delete_conversation_context as delete_lancedb_conversation_context,
        get_lancedb_connection,
    )

    LANCEDB_AVAILABLE = True
except ImportError:
    LANCEDB_AVAILABLE = False
    logging.warning("LanceDB integration not available - using SQL fallback")

# Try to import PostgreSQL utilities, fallback to SQLite
try:
    from db_utils import get_db_cursor, execute_query, execute_insert, execute_update

    DB_UTILS_AVAILABLE = True
except ImportError:
    try:
        from db_utils_fallback import (
            get_db_cursor,
            execute_query,
            execute_insert,
            execute_update,
        )

        DB_UTILS_AVAILABLE = True
    except ImportError:
        DB_UTILS_AVAILABLE = False

logger = logging.getLogger(__name__)


class ContextManagementService:
    """Service for managing conversation history and user preferences"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user preferences for a specific user"""
        if not DB_UTILS_AVAILABLE:
            return await self._create_default_preferences(user_id)

        try:
            query = """
                SELECT automation_level, communication_style, preferred_services, business_context
                FROM user_preferences
                WHERE user_id = %s
            """

            results = await execute_query(query, (user_id,))

            if results:
                preferences = results[0]
                return {
                    "automation_level": preferences.get("automation_level", "moderate"),
                    "communication_style": preferences.get(
                        "communication_style", "friendly"
                    ),
                    "preferred_services": preferences.get(
                        "preferred_services", ["gmail", "google_calendar", "notion"]
                    ),
                    "business_context": preferences.get(
                        "business_context",
                        {
                            "companySize": "solo",
                            "technicalSkill": "intermediate",
                            "goals": ["automation", "efficiency"],
                        },
                    ),
                }
            else:
                # Return default preferences if user doesn't have any
                return await self._create_default_preferences(user_id)

        except Exception as e:
            logger.error(f"Error getting user preferences for {user_id}: {e}")
            return await self._create_default_preferences(user_id)

    async def save_user_preferences(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> bool:
        """Save or update user preferences"""
        if not DB_UTILS_AVAILABLE:
            return True  # Silently succeed for fallback

        try:
            query = """
                INSERT INTO user_preferences
                (user_id, automation_level, communication_style, preferred_services, business_context)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    automation_level = EXCLUDED.automation_level,
                    communication_style = EXCLUDED.communication_style,
                    preferred_services = EXCLUDED.preferred_services,
                    business_context = EXCLUDED.business_context,
                    updated_at = CURRENT_TIMESTAMP
            """

            await execute_insert(
                query,
                (
                    user_id,
                    preferences.get("automation_level", "moderate"),
                    preferences.get("communication_style", "friendly"),
                    json.dumps(
                        preferences.get(
                            "preferred_services", ["gmail", "google_calendar", "notion"]
                        )
                    ),
                    json.dumps(
                        preferences.get(
                            "business_context",
                            {
                                "companySize": "solo",
                                "technicalSkill": "intermediate",
                                "goals": ["automation", "efficiency"],
                            },
                        )
                    ),
                ),
            )

            logger.info(f"Successfully saved preferences for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error saving preferences for user {user_id}: {e}")
            return False

    async def add_conversation_message(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Add a message to conversation history"""
        if not DB_UTILS_AVAILABLE:
            return True  # Silently succeed for fallback

        try:
            query = """
                INSERT INTO conversation_history
                (user_id, session_id, role, content, message_type, metadata)
                VALUES (%s, %s, %s, %s, %s, %s)
            """

            await execute_insert(
                query,
                (
                    user_id,
                    session_id,
                    role,
                    content,
                    message_type,
                    json.dumps(metadata or {}),
                ),
            )

            logger.debug(
                f"Added {role} message to conversation history for user {user_id}"
            )

            # Also store in LanceDB for semantic search if available
            if LANCEDB_AVAILABLE and content.strip():
                try:
                    # Generate embedding for semantic search
                    embedding = await self._generate_embedding(content)
                    if embedding:
                        conversation_data = {
                            "id": str(datetime.now().timestamp()),
                            "user_id": user_id,
                            "session_id": session_id,
                            "role": role,
                            "content": content,
                            "message_type": message_type,
                            "timestamp": datetime.now(),
                            "metadata": metadata or {},
                        }

                        db_conn = await get_lancedb_connection()
                        await store_conversation_context(
                            db_conn, conversation_data, embedding
                        )
                        logger.debug(
                            f"Stored conversation in LanceDB for semantic search"
                        )
                except Exception as e:
                    logger.warning(f"Failed to store conversation in LanceDB: {e}")
                    # Continue with SQL storage even if LanceDB fails

            return True

        except Exception as e:
            logger.error(f"Error adding conversation message for user {user_id}: {e}")
            return False

    async def get_conversation_history(
        self, user_id: str, session_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Get conversation history for a user, optionally filtered by session"""
        if not DB_UTILS_AVAILABLE:
            return []  # Return empty list for fallback

        try:
            if session_id:
                query = """
                    SELECT role, content, message_type, metadata, timestamp
                    FROM conversation_history
                    WHERE user_id = %s AND session_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """
                results = await execute_query(query, (user_id, session_id, limit))
            else:
                query = """
                    SELECT role, content, message_type, metadata, timestamp, session_id
                    FROM conversation_history
                    WHERE user_id = %s
                    ORDER BY timestamp DESC
                    LIMIT %s
                """
                results = await execute_query(query, (user_id, limit))

            # Process results to convert JSON fields
            history = []
            for row in results:
                history.append(
                    {
                        "role": row["role"],
                        "content": row["content"],
                        "message_type": row["message_type"],
                        "metadata": json.loads(row["metadata"])
                        if row["metadata"]
                        else {},
                        "timestamp": row["timestamp"],
                        "session_id": row.get("session_id")
                        if not session_id
                        else session_id,
                    }
                )

            # Return in chronological order (oldest first)
            return list(reversed(history))

        except Exception as e:
            logger.error(f"Error getting conversation history for user {user_id}: {e}")
            return []

    async def search_similar_conversations(
        self,
        user_id: str,
        query_text: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Search for similar conversations using semantic similarity"""
        if not LANCEDB_AVAILABLE:
            return []  # Return empty list if LanceDB not available

        try:
            # Generate embedding for the query
            query_embedding = await self._generate_embedding(query_text)
            if not query_embedding:
                return []

            # Search LanceDB for similar conversations
            db_conn = await get_lancedb_connection()
            search_result = await search_conversation_context(
                db_conn=db_conn,
                query_embedding=query_embedding,
                user_id=user_id,
                session_id=session_id,
                limit=limit,
                similarity_threshold=similarity_threshold,
            )

            if search_result.get("status") == "success":
                return search_result.get("results", [])
            else:
                logger.warning(f"LanceDB search failed: {search_result.get('message')}")
                return []

        except Exception as e:
            logger.error(
                f"Error searching similar conversations for user {user_id}: {e}"
            )
            return []

    async def get_contextual_conversation_history(
        self,
        user_id: str,
        current_message: str,
        session_id: Optional[str] = None,
        semantic_limit: int = 5,
        chronological_limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Get conversation history enhanced with semantic context"""
        try:
            # Get chronological history
            chronological_history = await self.get_conversation_history(
                user_id, session_id, chronological_limit
            )

            # Get semantically similar conversations
            semantic_history = await self.search_similar_conversations(
                user_id, current_message, session_id, semantic_limit
            )

            # Combine and deduplicate results
            combined_history = []
            seen_ids = set()

            # Add semantic matches first (most relevant)
            for conv in semantic_history:
                conv_id = f"{conv.get('timestamp')}-{conv.get('content')[:50]}"
                if conv_id not in seen_ids:
                    combined_history.append(conv)
                    seen_ids.add(conv_id)

            # Add chronological history (recent conversations)
            for conv in chronological_history:
                conv_id = f"{conv.get('timestamp')}-{conv.get('content')[:50]}"
                if conv_id not in seen_ids:
                    combined_history.append(conv)
                    seen_ids.add(conv_id)

            # Sort by timestamp (most recent first)
            combined_history.sort(
                key=lambda x: x.get("timestamp", datetime.min), reverse=True
            )

            return combined_history[: chronological_limit + semantic_limit]

        except Exception as e:
            logger.error(
                f"Error getting contextual conversation history for user {user_id}: {e}"
            )
            # Fallback to chronological history
            return await self.get_conversation_history(
                user_id, session_id, chronological_limit
            )

    async def clear_conversation_history(
        self, user_id: str, session_id: Optional[str] = None
    ) -> bool:
        """Clear conversation history for a user, optionally for a specific session"""
        if not DB_UTILS_AVAILABLE:
            return True  # Silently succeed for fallback

        try:
            if session_id:
                query = "DELETE FROM conversation_history WHERE user_id = %s AND session_id = %s"
                await execute_update(query, (user_id, session_id))
                logger.info(
                    f"Cleared conversation history for user {user_id}, session {session_id}"
                )
            else:
                query = "DELETE FROM conversation_history WHERE user_id = %s"
                await execute_update(query, (user_id,))
                logger.info(f"Cleared all conversation history for user {user_id}")

            # Also clear from LanceDB if available
            if LANCEDB_AVAILABLE:
                try:
                    db_conn = await get_lancedb_connection()
                    await delete_lancedb_conversation_context(
                        db_conn, user_id, session_id
                    )
                    logger.info(
                        f"Cleared LanceDB conversation context for user {user_id}"
                    )
                except Exception as e:
                    logger.warning(f"Failed to clear LanceDB conversation context: {e}")

            return True

        except Exception as e:
            logger.error(f"Error clearing conversation history for user {user_id}: {e}")
            return False

    async def get_or_create_chat_context(
        self, user_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Get or create chat context for a user session"""
        if not DB_UTILS_AVAILABLE:
            return await self._create_chat_context(user_id, session_id)

        try:
            query = """
                SELECT session_id, active_workflows, context_data
                FROM chat_contexts
                WHERE user_id = %s
            """

            results = await execute_query(query, (user_id,))

            if results:
                context = results[0]
                return {
                    "user_id": user_id,
                    "session_id": context["session_id"],
                    "active_workflows": json.loads(context["active_workflows"])
                    if context["active_workflows"]
                    else [],
                    "context_data": json.loads(context["context_data"])
                    if context["context_data"]
                    else {},
                }
            else:
                # Create new context
                return await self._create_chat_context(user_id, session_id)

        except Exception as e:
            logger.error(f"Error getting chat context for user {user_id}: {e}")
            return await self._create_chat_context(user_id, session_id)

    async def update_chat_context(
        self,
        user_id: str,
        session_id: str,
        active_workflows: List[str],
        context_data: Dict[str, Any],
    ) -> bool:
        """Update chat context for a user"""
        if not DB_UTILS_AVAILABLE:
            return True  # Silently succeed for fallback

        try:
            query = """
                INSERT INTO chat_contexts
                (user_id, session_id, active_workflows, context_data)
                VALUES (%s, %s, %s, %s)
                ON CONFLICT (user_id)
                DO UPDATE SET
                    session_id = EXCLUDED.session_id,
                    active_workflows = EXCLUDED.active_workflows,
                    context_data = EXCLUDED.context_data,
                    updated_at = CURRENT_TIMESTAMP
            """

            await execute_insert(
                query,
                (
                    user_id,
                    session_id,
                    json.dumps(active_workflows),
                    json.dumps(context_data),
                ),
            )

            logger.debug(f"Updated chat context for user {user_id}")
            return True

        except Exception as e:
            logger.error(f"Error updating chat context for user {user_id}: {e}")
            return False

    async def get_context_aware_workflow_suggestions(
        self, user_id: str
    ) -> List[Dict[str, Any]]:
        """Get workflow suggestions based on user context and preferences"""
        try:
            preferences = await self.get_user_preferences(user_id)
            conversation_history = await self.get_conversation_history(
                user_id, limit=10
            )
            chat_context = await self.get_or_create_chat_context(user_id, "current")

            # Analyze recent conversations for workflow opportunities
            suggestions = self._analyze_conversation_for_workflows(
                conversation_history, preferences
            )

            # Add context-based suggestions
            context_suggestions = self._generate_context_suggestions(
                chat_context, preferences
            )
            suggestions.extend(context_suggestions)

            return suggestions[:10]  # Limit to top 10 suggestions

        except Exception as e:
            logger.error(
                f"Error getting context-aware suggestions for user {user_id}: {e}"
            )
            return []

    async def _create_default_preferences(self, user_id: str) -> Dict[str, Any]:
        """Create default preferences for a user"""
        default_preferences = {
            "automation_level": "moderate",
            "communication_style": "friendly",
            "preferred_services": ["gmail", "google_calendar", "notion"],
            "business_context": {
                "companySize": "solo",
                "technicalSkill": "intermediate",
                "goals": ["automation", "efficiency"],
            },
        }

        # Save the default preferences
        await self.save_user_preferences(user_id, default_preferences)
        return default_preferences

    async def _create_chat_context(
        self, user_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Create a new chat context for a user"""
        default_context = {
            "user_id": user_id,
            "session_id": session_id,
            "active_workflows": [],
            "context_data": {},
        }

        # Save the context
        await self.update_chat_context(user_id, session_id, [], {})
        return default_context

    def _analyze_conversation_for_workflows(
        self, conversation_history: List[Dict[str, Any]], preferences: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Analyze conversation history to suggest relevant workflows"""
        suggestions = []

        # Look for patterns in recent conversations
        recent_messages = conversation_history[-5:]  # Last 5 messages

        for message in recent_messages:
            content = message["content"].lower()

            # Check for email-related patterns
            if any(word in content for word in ["email", "inbox", "message"]):
                suggestions.append(
                    {
                        "name": "Email Management Workflow",
                        "description": "Automate email processing and organization",
                        "services": ["gmail"],
                        "confidence": 0.7,
                    }
                )

            # Check for calendar-related patterns
            if any(
                word in content
                for word in ["meeting", "calendar", "schedule", "appointment"]
            ):
                suggestions.append(
                    {
                        "name": "Meeting Automation Workflow",
                        "description": "Automate meeting scheduling and follow-ups",
                        "services": ["google_calendar"],
                        "confidence": 0.8,
                    }
                )

            # Check for task-related patterns
            if any(
                word in content for word in ["task", "todo", "reminder", "deadline"]
            ):
                suggestions.append(
                    {
                        "name": "Task Management Workflow",
                        "description": "Automate task creation and tracking",
                        "services": ["notion", "asana", "trello"],
                        "confidence": 0.75,
                    }
                )

        return suggestions

    def _generate_context_suggestions(
        self, chat_context: Dict[str, Any], preferences: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """Generate workflow suggestions based on user context"""
        suggestions = []

        # Suggest based on preferred services
        preferred_services = preferences.get("preferred_services", [])

        if "gmail" in preferred_services:
            suggestions.append(
                {
                    "name": "Smart Email Categorization",
                    "description": "Automatically categorize and prioritize emails",
                    "services": ["gmail"],
                    "confidence": 0.9,
                }
            )

        if "google_calendar" in preferred_services:
            suggestions.append(
                {
                    "name": "Meeting Preparation Assistant",
                    "description": "Prepare meeting materials and send reminders",
                    "services": ["google_calendar"],
                    "confidence": 0.85,
                }
            )

        if "notion" in preferred_services:
            suggestions.append(
                {
                    "name": "Document Organization Workflow",
                    "description": "Automatically organize documents and notes",
                    "services": ["notion"],
                    "confidence": 0.8,
                }
            )

        return suggestions

    def _extract_context_from_history(
        self, conversation_history: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Extract relevant context from conversation history"""
        context = {
            "recent_topics": [],
            "frequent_services": [],
            "workflow_patterns": [],
        }

        if not conversation_history:
            return context

        # Analyze last 5 messages for context
        recent_messages = conversation_history[-5:]

        # Extract topics and services mentioned
        services_mentioned = set()
        topics = set()

        for message in recent_messages:
            content = message["content"].lower()

            # Check for service mentions
            service_keywords = {
                "gmail": ["email", "inbox", "message"],
                "google_calendar": ["meeting", "calendar", "schedule", "appointment"],
                "notion": ["note", "document", "page", "database"],
                "asana": ["task", "project", "todo"],
                "slack": ["message", "channel", "notification"],
                "trello": ["board", "card", "list"],
            }

            for service, keywords in service_keywords.items():
                if any(keyword in content for keyword in keywords):
                    services_mentioned.add(service)

            # Extract potential topics
            if "email" in content:
                topics.add("email_management")
            if "meeting" in content:
                topics.add("meeting_management")
            if "task" in content:
                topics.add("task_management")
            if "file" in content:
                topics.add("file_management")

        context["recent_topics"] = list(topics)
        context["frequent_services"] = list(services_mentioned)

        return context

    async def _generate_embedding(self, text: str) -> Optional[List[float]]:
        """Generate embedding for text using available embedding service"""
        try:
            # Try to use OpenAI embeddings if available
            try:
                from openai import OpenAI
                import os

                client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
                response = client.embeddings.create(
                    input=text, model="text-embedding-3-small"
                )
                return response.data[0].embedding
            except ImportError:
                # Fallback to simple TF-IDF like embedding
                return self._generate_simple_embedding(text)

        except Exception as e:
            logger.warning(f"Failed to generate embedding: {e}")
            return None

    def _generate_simple_embedding(self, text: str) -> List[float]:
        """Generate a simple embedding using word frequency"""
        # Simple word frequency based embedding (placeholder)
        # In production, this should use a proper embedding model
        words = text.lower().split()
        word_freq = {}
        for word in words:
            word_freq[word] = word_freq.get(word, 0) + 1

        # Create a simple 50-dimensional embedding based on word frequencies
        embedding = [0.0] * 50
        for i, (word, freq) in enumerate(word_freq.items()):
            if i < 50:
                # Simple hash-based distribution
                hash_val = hash(word) % 50
                embedding[hash_val] += freq * 0.1

        # Normalize the embedding
        norm = sum(x * x for x in embedding) ** 0.5
        if norm > 0:
            embedding = [x / norm for x in embedding]

        return embedding

    def get_user_context_summary(self, user_id: str) -> Dict[str, Any]:
        """Get a comprehensive summary of user context"""
        try:
            preferences = self.get_user_preferences_sync(user_id)
            conversation_history = self.get_conversation_history_sync(user_id, limit=20)
            chat_context = self.get_or_create_chat_context_sync(user_id, "current")

            return {
                "user_id": user_id,
                "preferences": preferences,
                "recent_conversations": len(conversation_history),
                "active_workflows": len(chat_context.get("active_workflows", [])),
                "business_context": preferences.get("business_context", {}),
                "preferred_services": preferences.get("preferred_services", []),
            }

        except Exception as e:
            logger.error(f"Error getting user context summary for {user_id}: {e}")
            return {}

    # Synchronous wrapper methods for use in synchronous contexts
    def get_user_preferences_sync(self, user_id: str) -> Dict[str, Any]:
        """Synchronous wrapper for get_user_preferences"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.get_user_preferences(user_id)
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(self.get_user_preferences(user_id))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.get_user_preferences(user_id))

    def save_user_preferences_sync(
        self, user_id: str, preferences: Dict[str, Any]
    ) -> bool:
        """Synchronous wrapper for save_user_preferences"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.save_user_preferences(user_id, preferences)
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(self.save_user_preferences(user_id, preferences))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.save_user_preferences(user_id, preferences))

    def search_similar_conversations_sync(
        self,
        user_id: str,
        query_text: str,
        session_id: Optional[str] = None,
        limit: int = 10,
        similarity_threshold: float = 0.7,
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for search_similar_conversations"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.search_similar_conversations(
                            user_id, query_text, session_id, limit, similarity_threshold
                        ),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(
                    self.search_similar_conversations(
                        user_id, query_text, session_id, limit, similarity_threshold
                    )
                )
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(
                self.search_similar_conversations(
                    user_id, query_text, session_id, limit, similarity_threshold
                )
            )

    def get_contextual_conversation_history_sync(
        self,
        user_id: str,
        current_message: str,
        session_id: Optional[str] = None,
        semantic_limit: int = 5,
        chronological_limit: int = 10,
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_contextual_conversation_history"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.get_contextual_conversation_history(
                            user_id,
                            current_message,
                            session_id,
                            semantic_limit,
                            chronological_limit,
                        ),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(
                    self.get_contextual_conversation_history(
                        user_id,
                        current_message,
                        session_id,
                        semantic_limit,
                        chronological_limit,
                    )
                )
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(
                self.get_contextual_conversation_history(
                    user_id,
                    current_message,
                    session_id,
                    semantic_limit,
                    chronological_limit,
                )
            )

    def add_conversation_message_sync(
        self,
        user_id: str,
        session_id: str,
        role: str,
        content: str,
        message_type: str = "text",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Synchronous wrapper for add_conversation_message"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.add_conversation_message(
                            user_id, session_id, role, content, message_type, metadata
                        ),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(
                    self.add_conversation_message(
                        user_id, session_id, role, content, message_type, metadata
                    )
                )
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(
                self.add_conversation_message(
                    user_id, session_id, role, content, message_type, metadata
                )
            )

    def get_conversation_history_sync(
        self, user_id: str, session_id: Optional[str] = None, limit: int = 50
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_conversation_history"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.get_conversation_history(user_id, session_id, limit),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(
                    self.get_conversation_history(user_id, session_id, limit)
                )
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(
                self.get_conversation_history(user_id, session_id, limit)
            )

    def get_or_create_chat_context_sync(
        self, user_id: str, session_id: str
    ) -> Dict[str, Any]:
        """Synchronous wrapper for get_or_create_chat_context"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.get_or_create_chat_context(user_id, session_id),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(self.get_or_create_chat_context(user_id, session_id))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.get_or_create_chat_context(user_id, session_id))

    def update_chat_context_sync(
        self,
        user_id: str,
        session_id: str,
        active_workflows: List[str],
        context_data: Dict[str, Any],
    ) -> bool:
        """Synchronous wrapper for update_chat_context"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.update_chat_context(
                            user_id, session_id, active_workflows, context_data
                        ),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(
                    self.update_chat_context(
                        user_id, session_id, active_workflows, context_data
                    )
                )
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(
                self.update_chat_context(
                    user_id, session_id, active_workflows, context_data
                )
            )

    def get_context_aware_workflow_suggestions_sync(
        self, user_id: str
    ) -> List[Dict[str, Any]]:
        """Synchronous wrapper for get_context_aware_workflow_suggestions"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.get_context_aware_workflow_suggestions(user_id),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(self.get_context_aware_workflow_suggestions(user_id))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.get_context_aware_workflow_suggestions(user_id))

    def get_user_context_summary_sync(self, user_id: str) -> Dict[str, Any]:
        """Synchronous wrapper for get_user_context_summary"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run, self.get_user_context_summary(user_id)
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(self.get_user_context_summary(user_id))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.get_user_context_summary(user_id))

    def clear_conversation_history_sync(
        self, user_id: str, session_id: Optional[str] = None
    ) -> bool:
        """Synchronous wrapper for clear_conversation_history"""
        import asyncio

        try:
            # Try to get the current event loop
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # If loop is running, use run_coroutine_threadsafe
                import concurrent.futures

                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(
                        asyncio.run,
                        self.clear_conversation_history(user_id, session_id),
                    )
                    return future.result()
            else:
                # If no running loop, use asyncio.run
                return asyncio.run(self.clear_conversation_history(user_id, session_id))
        except RuntimeError:
            # No event loop, use asyncio.run
            return asyncio.run(self.clear_conversation_history(user_id, session_id))


# Global instance
context_management_service = ContextManagementService()
