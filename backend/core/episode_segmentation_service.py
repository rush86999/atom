"""
Episode Segmentation Service

Automatically segments agent interactions into coherent episodes using:
- Time gap detection (30-minute threshold)
- Topic change detection (semantic similarity < 0.75)
- Task completion detection

Archives episodes to LanceDB for semantic search.
"""

from datetime import datetime, timedelta
import logging
import os
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.lancedb_handler import get_lancedb_handler
from core.models import (
    AgentExecution,
    AgentFeedback,
    AgentRegistry,
    AgentStatus,
    CanvasAudit,
    ChatMessage,
    ChatSession,
    Episode,
    EpisodeSegment,
    User,
)

logger = logging.getLogger(__name__)

# Configuration
TIME_GAP_THRESHOLD_MINUTES = 30
SEMANTIC_SIMILARITY_THRESHOLD = 0.75


class EpisodeBoundaryDetector:
    """Detects episode boundaries using multiple signals"""

    def __init__(self, lancedb_handler):
        self.db = lancedb_handler

    def detect_time_gap(self, messages: List[ChatMessage]) -> List[int]:
        """Detect time gaps > threshold between messages"""
        gaps = []
        for i in range(1, len(messages)):
            prev_time = messages[i-1].created_at
            curr_time = messages[i].created_at
            gap_minutes = (curr_time - prev_time).total_seconds() / 60

            if gap_minutes >= TIME_GAP_THRESHOLD_MINUTES:
                gaps.append(i)

        return gaps

    def detect_topic_changes(self, messages: List[ChatMessage]) -> List[int]:
        """Detect topic changes using semantic similarity"""
        if not self.db or len(messages) < 2:
            return []

        changes = []
        for i in range(1, len(messages)):
            # Get embeddings for consecutive messages
            prev_embedding = self.db.embed_text(messages[i-1].content)
            curr_embedding = self.db.embed_text(messages[i].content)

            if prev_embedding is None or curr_embedding is None:
                continue

            # Calculate cosine similarity
            similarity = self._cosine_similarity(prev_embedding, curr_embedding)

            if similarity < SEMANTIC_SIMILARITY_THRESHOLD:
                changes.append(i)

        return changes

    def detect_task_completion(self, executions: List[AgentExecution]) -> List[int]:
        """Detect task completion markers"""
        completions = []
        for i, exec in enumerate(executions):
            if exec.status == "completed" and exec.result_summary:
                completions.append(i)

        return completions

    def _cosine_similarity(self, vec1, vec2) -> float:
        """Calculate cosine similarity between two vectors"""
        try:
            # Try numpy first (if available)
            import numpy as np
            v1 = np.array(vec1) if not isinstance(vec1, np.ndarray) else vec1
            v2 = np.array(vec2) if not isinstance(vec2, np.ndarray) else vec2
            return float(np.dot(v1, v2) / (np.linalg.norm(v1) * np.linalg.norm(v2)))
        except (ImportError, ValueError, TypeError) as e:
            # Fallback to pure Python implementation
            logger.debug(f"Numpy calculation failed, using pure Python: {e}")
            import math
            try:
                # Calculate dot product
                dot_product = sum(a * b for a, b in zip(vec1, vec2))

                # Calculate magnitudes
                magnitude1 = math.sqrt(sum(a * a for a in vec1))
                magnitude2 = math.sqrt(sum(b * b for b in vec2))

                # Avoid division by zero
                if magnitude1 == 0 or magnitude2 == 0:
                    return 0.0

                return dot_product / (magnitude1 * magnitude2)
            except (ValueError, TypeError, ZeroDivisionError) as e:
                logger.warning(f"Cosine similarity calculation failed: {e}")
                return 0.0


class EpisodeSegmentationService:
    """Creates episodes from agent sessions and executions"""

    def __init__(self, db: Session):
        self.db = db
        self.lancedb = get_lancedb_handler()
        self.detector = EpisodeBoundaryDetector(self.lancedb)

    async def create_episode_from_session(
        self,
        session_id: str,
        agent_id: str,
        title: Optional[str] = None,
        force_create: bool = False
    ) -> Optional[Episode]:
        """
        Main method: Create episode from chat session

        Args:
            session_id: ChatSession ID
            agent_id: Agent ID
            title: Optional title (auto-generated if not provided)
            force_create: Force episode creation even if small

        Returns:
            Created Episode object or None
        """
        # 1. Fetch session data
        session = self.db.query(ChatSession).filter(
            ChatSession.id == session_id
        ).first()

        if not session:
            logger.error(f"Session {session_id} not found")
            return None

        # 2. Get messages and executions
        messages = self.db.query(ChatMessage).filter(
            ChatMessage.session_id == session_id
        ).order_by(ChatMessage.created_at.asc()).all()

        executions = self.db.query(AgentExecution).filter(
            AgentExecution.session_id == session_id
        ).order_by(AgentExecution.created_at.asc()).all()

        # 2.5. Fetch canvas and feedback context (NEW)
        canvas_audits = self._fetch_canvas_context(session_id)
        feedback_records = self._fetch_feedback_context(session_id, agent_id, [e.id for e in executions])

        if not messages and not executions:
            logger.warning(f"No data for session {session_id}")
            return None

        # Check minimum size (unless forced)
        total_items = len(messages) + len(executions)
        if total_items < 2 and not force_create:
            logger.info(f"Session {session_id} too small for episode ({total_items} items)")
            return None

        # 3. Detect boundaries
        message_boundaries = set()
        message_boundaries.update(self.detector.detect_time_gap(messages))
        message_boundaries.update(self.detector.detect_topic_changes(messages))

        # 4. Create episode
        episode = Episode(
            id=str(uuid.uuid4()),
            title=title or self._generate_title(messages, executions),
            description=self._generate_description(messages, executions),
            summary=self._generate_summary(messages, executions),
            agent_id=agent_id,
            user_id=session.user_id,
            workspace_id=session.workspace_id or "default",
            session_id=session_id,
            execution_ids=[e.id for e in executions],
            # NEW - Canvas and feedback linkage
            canvas_ids=[c.id for c in canvas_audits],
            canvas_action_count=len(canvas_audits),
            feedback_ids=[f.id for f in feedback_records],
            aggregate_feedback_score=self._calculate_feedback_score(feedback_records),
            started_at=messages[0].created_at if messages else executions[0].created_at,
            ended_at=messages[-1].created_at if messages else executions[-1].created_at,
            duration_seconds=self._calculate_duration(messages, executions),
            status="completed",
            topics=self._extract_topics(messages, executions),
            entities=self._extract_entities(messages, executions),
            importance_score=self._calculate_importance(messages, executions),
            # Graduation fields
            maturity_at_time=self._get_agent_maturity(agent_id),
            human_intervention_count=self._count_interventions(executions),
            human_edits=self._extract_human_edits(executions),
            constitutional_score=None,  # Calculated separately
            world_model_state=self._get_world_model_version()
        )

        self.db.add(episode)
        self.db.commit()
        self.db.refresh(episode)

        # 4.5. Link back to source records (NEW)
        # Update CanvasAudit with episode_id
        for canvas in canvas_audits:
            canvas.episode_id = episode.id

        # Update AgentFeedback with episode_id
        for feedback in feedback_records:
            feedback.episode_id = episode.id

        self.db.commit()

        # 5. Create segments
        await self._create_segments(episode, messages, executions, message_boundaries)

        # 6. Archive to LanceDB
        await self._archive_to_lancedb(episode)

        logger.info(f"Created episode {episode.id} from session {session_id}")
        return episode

    def _generate_title(self, messages, executions) -> str:
        """Generate episode title using LLM or heuristics"""
        # Simple heuristic for now
        if messages:
            first_user_msg = next((m for m in messages if m.role == "user"), None)
            if first_user_msg:
                # Truncate to 50 chars
                content = first_user_msg.content
                if len(content) > 50:
                    return content[:47] + "..."
                return content

        return f"Episode from {datetime.now().strftime('%Y-%m-%d %H:%M')}"

    def _generate_description(self, messages, executions) -> str:
        """Generate episode description"""
        msg_count = len(messages)
        exec_count = len(executions)
        return f"Episode with {msg_count} messages and {exec_count} executions"

    def _generate_summary(self, messages, executions) -> str:
        """Generate episode summary"""
        # For now, just concatenate first and last messages
        if messages:
            first_content = messages[0].content[:100]
            last_content = messages[-1].content[:100]
            return f"Started: {first_content}...\nEnded: {last_content}"
        return "Episode summary"

    def _calculate_duration(self, messages, executions) -> Optional[int]:
        """Calculate episode duration in seconds"""
        all_timestamps = []

        for m in messages:
            if m.created_at:
                all_timestamps.append(m.created_at)

        for e in executions:
            if e.created_at:
                all_timestamps.append(e.created_at)
            if e.completed_at:
                all_timestamps.append(e.completed_at)

        if len(all_timestamps) < 2:
            return None

        all_timestamps.sort()
        duration = (all_timestamps[-1] - all_timestamps[0]).total_seconds()
        return int(duration)

    def _extract_topics(self, messages, executions) -> List[str]:
        """Extract topics from episode content"""
        # Simple keyword extraction for now
        topics = set()

        for m in messages:
            # Extract common words as topics (very basic)
            words = m.content.lower().split()
            topics.update([w for w in words if len(w) > 4][:3])

        return list(topics)[:5]

    def _extract_entities(self, messages, executions) -> List[str]:
        """Extract named entities from episode using regex-based NLP"""
        import re
        entities = set()

        # Extract from messages
        for msg in messages:
            # Email addresses
            emails = re.findall(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b', msg.content)
            entities.update(emails)

            # Phone numbers (US format)
            phones = re.findall(r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b', msg.content)
            entities.update(phones)

            # URLs
            urls = re.findall(r'https?://[^\s<>"{}|\\^`\[\]]+', msg.content)
            entities.update(urls)

            # Extract from metadata if available (ChatMessage may not have this field)
            metadata = getattr(msg, 'metadata_json', None)
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, str) and 3 < len(value) < 50:
                        # Filter for likely entities (alphanumeric with some special chars)
                        if re.match(r'^[A-Za-z0-9._@-]+$', value):
                            entities.add(value)

        # Extract from executions
        for exec in executions:
            # Try multiple field names for task description
            task_desc = getattr(exec, 'task_description', None) or \
                       getattr(exec, 'input_summary', None) or \
                       getattr(exec, 'output_summary', None)

            if task_desc:
                # Extract task-related entities
                words = task_desc.split()
                # Capitalized words might be proper nouns
                for word in words:
                    if word[0].isupper() and len(word) > 3:
                        entities.add(word)

            # Extract from execution metadata if available
            metadata = getattr(exec, 'metadata_json', None)
            if metadata:
                for key, value in metadata.items():
                    if isinstance(value, str) and 3 < len(value) < 50:
                        entities.add(value)

        # Return limited list to avoid overwhelming
        return list(entities)[:20]

    def _calculate_importance(self, messages, executions) -> float:
        """Calculate episode importance score (0.0 to 1.0)"""
        # Simple heuristic based on activity
        score = 0.5  # Base score

        # More messages = higher importance
        if len(messages) > 10:
            score += 0.2
        elif len(messages) > 5:
            score += 0.1

        # Executions increase importance
        if len(executions) > 0:
            score += 0.1

        return min(1.0, score)

    def _get_agent_maturity(self, agent_id: str) -> str:
        """Get current agent maturity level"""
        agent = self.db.query(AgentRegistry).filter(
            AgentRegistry.id == agent_id
        ).first()

        if agent:
            if hasattr(agent.status, 'value'):
                return agent.status.value
            return str(agent.status)

        return "STUDENT"

    def _count_interventions(self, executions: List[AgentExecution]) -> int:
        """Count human interventions during episode"""
        count = 0
        for exec in executions:
            # Check if execution had human intervention
            if exec.metadata_json and exec.metadata_json.get("human_intervention"):
                count += 1
        return count

    def _extract_human_edits(self, executions: List[AgentExecution]) -> List[Dict[str, Any]]:
        """Extract human corrections during episode"""
        edits = []
        for exec in executions:
            if exec.metadata_json and exec.metadata_json.get("human_corrections"):
                edits.extend(exec.metadata_json["human_corrections"])
        return edits

    def _get_world_model_version(self) -> str:
        """Get current world model version from environment or configuration"""
        # Check environment variable first
        version = os.getenv("WORLD_MODEL_VERSION")
        if version:
            return version

        # Check database for version configuration
        try:
            from core.models import SystemConfig
            config = self.db.query(SystemConfig).filter(
                SystemConfig.key == "world_model_version"
            ).first()

            if config and config.value:
                return config.value
        except Exception as e:
            logger.debug(f"Could not fetch world model version from DB: {e}")

        # Return default version
        return "v1.0"

    async def _create_segments(
        self,
        episode: Episode,
        messages: List[ChatMessage],
        executions: List[AgentExecution],
        boundaries: set
    ):
        """Create episode segments from messages and executions"""
        segment_order = 0

        # Create conversation segments from messages
        if messages:
            current_segment_messages = []

            for i, msg in enumerate(messages):
                current_segment_messages.append(msg)

                # Create segment at boundaries
                if i in boundaries or i == len(messages) - 1:
                    if current_segment_messages:
                        segment = EpisodeSegment(
                            id=str(uuid.uuid4()),
                            episode_id=episode.id,
                            segment_type="conversation",
                            sequence_order=segment_order,
                            content=self._format_messages(current_segment_messages),
                            content_summary=self._summarize_messages(current_segment_messages),
                            source_type="chat_message",
                            source_id=current_segment_messages[0].id
                        )
                        self.db.add(segment)
                        segment_order += 1
                        current_segment_messages = []

        # Create execution segments
        for exec in executions:
            segment = EpisodeSegment(
                id=str(uuid.uuid4()),
                episode_id=episode.id,
                segment_type="execution",
                sequence_order=segment_order,
                content=self._format_execution(exec),
                content_summary=exec.result_summary or "Agent execution",
                source_type="agent_execution",
                source_id=exec.id
            )
            self.db.add(segment)
            segment_order += 1

        self.db.commit()

    def _format_messages(self, messages: List[ChatMessage]) -> str:
        """Format messages as text"""
        return "\n".join([
            f"{m.role}: {m.content}"
            for m in messages
        ])

    def _summarize_messages(self, messages: List[ChatMessage]) -> str:
        """Summarize messages"""
        if not messages:
            return ""

        first_msg = messages[0].content[:50]
        if len(messages) == 1:
            return first_msg
        return f"{first_msg}... ({len(messages)} messages)"

    def _format_execution(self, exec: AgentExecution) -> str:
        """Format execution as text"""
        parts = [
            f"Task: {exec.task_description or 'Unknown'}",
            f"Status: {exec.status}"
        ]

        if exec.result_summary:
            parts.append(f"Result: {exec.result_summary}")

        return "\n".join(parts)

    async def _archive_to_lancedb(self, episode: Episode):
        """Archive episode to LanceDB for semantic search"""
        if not self.lancedb.db:
            logger.warning("LanceDB not available, skipping archival")
            return

        try:
            # Combine episode content for embedding
            content = f"""
Title: {episode.title}
Description: {episode.description}
Summary: {episode.summary}
Topics: {', '.join(episode.topics)}
            """.strip()

            metadata = {
                "episode_id": episode.id,
                "agent_id": episode.agent_id,
                "user_id": episode.user_id,
                "workspace_id": episode.workspace_id,
                "session_id": episode.session_id,
                "status": episode.status,
                "topics": episode.topics,
                "maturity_at_time": episode.maturity_at_time,
                "human_intervention_count": episode.human_intervention_count,
                "constitutional_score": episode.constitutional_score,
                "type": "episode"
            }

            # Create episodes table if it doesn't exist
            table_name = "episodes"
            if table_name not in self.lancedb.db.table_names():
                self.lancedb.create_table(table_name)

            # Add to LanceDB
            self.lancedb.add_document(
                table_name=table_name,
                text=content,
                source=f"episode:{episode.id}",
                metadata=metadata,
                user_id=episode.user_id or "system",
                extract_knowledge=False
            )

            logger.info(f"Archived episode {episode.id} to LanceDB")

        except Exception as e:
            logger.error(f"Failed to archive episode to LanceDB: {e}")

    def _fetch_canvas_context(self, session_id: str) -> List[CanvasAudit]:
        """
        Fetch all canvas events for a session during episode creation.

        Args:
            session_id: ChatSession ID

        Returns:
            List of CanvasAudit records ordered by creation time
        """
        try:
            canvases = self.db.query(CanvasAudit).filter(
                CanvasAudit.session_id == session_id
            ).order_by(CanvasAudit.created_at.asc()).all()

            logger.debug(f"Found {len(canvases)} canvas events for session {session_id}")
            return canvases

        except Exception as e:
            logger.error(f"Failed to fetch canvas context for session {session_id}: {e}")
            return []

    def _fetch_feedback_context(
        self,
        session_id: str,
        agent_id: str,
        execution_ids: List[str]
    ) -> List[AgentFeedback]:
        """
        Fetch feedback for session/agent during episode creation.

        Queries by agent_execution_id linkage to capture feedback related
        to executions in this session.

        Args:
            session_id: ChatSession ID
            agent_id: Agent ID
            execution_ids: List of AgentExecution IDs in this session

        Returns:
            List of AgentFeedback records
        """
        try:
            if not execution_ids:
                return []

            # Query feedback by agent_execution_id linkage
            feedbacks = self.db.query(AgentFeedback).filter(
                AgentFeedback.agent_id == agent_id,
                AgentFeedback.agent_execution_id.in_(execution_ids)
            ).all()

            logger.debug(f"Found {len(feedbacks)} feedback records for agent {agent_id}")
            return feedbacks

        except Exception as e:
            logger.error(f"Failed to fetch feedback context for session {session_id}: {e}")
            return []

    def _calculate_feedback_score(self, feedbacks: List[AgentFeedback]) -> Optional[float]:
        """
        Calculate aggregate feedback score (-1.0 to 1.0).

        Scoring:
        - thumbs_up: +1.0
        - thumbs_down: -1.0
        - rating 1-5: converted to -1.0 to 1.0 scale

        Args:
            feedbacks: List of AgentFeedback records

        Returns:
            Aggregate score or None if no feedback
        """
        if not feedbacks:
            return None

        try:
            scores = []
            for f in feedbacks:
                if f.feedback_type == "thumbs_up" or f.thumbs_up_down is True:
                    scores.append(1.0)
                elif f.feedback_type == "thumbs_down" or f.thumbs_up_down is False:
                    scores.append(-1.0)
                elif f.feedback_type == "rating" and f.rating:
                    # Convert 1-5 scale to -1.0 to 1.0
                    # 1 -> -1.0, 2 -> -0.5, 3 -> 0.0, 4 -> 0.5, 5 -> 1.0
                    scores.append((f.rating - 3) / 2)

            if not scores:
                return None

            aggregate = sum(scores) / len(scores)
            logger.debug(f"Calculated aggregate feedback score: {aggregate:.2f}")
            return aggregate

        except Exception as e:
            logger.error(f"Failed to calculate feedback score: {e}")
            return None
