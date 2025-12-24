"""
Chat Context Manager
Handles context extraction and entity resolution from chat history.
"""

import logging
from typing import List, Dict, Any, Optional
from core.lancedb_handler import get_lancedb_handler, LanceDBHandler

logger = logging.getLogger(__name__)

class ChatContextManager:
    """
    Manages context resolution for chat conversations.
    Uses LanceDB to find relevant past entities and resolve references.
    """
    
    def __init__(self, lancedb_handler: LanceDBHandler = None):
        self.db = lancedb_handler or get_lancedb_handler()
        
    async def resolve_reference(
        self,
        text: str,
        session_id: str,
        entity_type: str = None
    ) -> Optional[Dict[str, Any]]:
        """
        Resolve a reference (e.g., "that workflow", "it") to a specific entity.
        
        Args:
            text: The text containing the reference (or the whole message)
            session_id: The current session ID
            entity_type: Optional filter (e.g., "workflow", "task")
            
        Returns:
            Dict containing entity info (id, type, name) or None
        """
        logger.info(f"resolve_reference called with session_id={session_id}, entity_type={entity_type}")
        if not self.db:
            logger.error("resolve_reference: DB is None")
            return None
        if not session_id:
            logger.error("resolve_reference: session_id is None")
            return None
            
        try:
            # 1. Look for recent entities in the session history
            # We want the MOST RECENT mention of the entity type
            
            # Get recent messages from this session
            # We fetch more history to be safe
            table_name = "chat_messages"
            table = self.db.get_table(table_name)
            if not table:
                return None
                
            # Search for messages in this session that have entities in metadata
            # We can't easily query JSON fields in LanceDB SQL yet, so we fetch recent session messages
            # and filter in python.
            
            # Get last 10 messages from session
            results = table.search().where(f"metadata LIKE '%{session_id}%'").limit(20).to_pandas()
            
            logger.info(f"Context resolution: Found {len(results)} messages for session {session_id}")
            
            # Sort by created_at descending (newest first)
            results = results.sort_values('created_at', ascending=False)
            
            import json
            
            for _, row in results.iterrows():
                try:
                    metadata = json.loads(row['metadata']) if row['metadata'] else {}
                    logger.info(f"Checking message {row['id']} metadata: {metadata}")
                    
                    # Check if this message has entities
                    entities = metadata.get('entities', {})
                    
                    # If looking for specific type
                    if entity_type:
                        # Check specific ID fields first
                        if entity_type == "workflow" and metadata.get('workflow_id'):
                            logger.info(f"Found workflow_id in metadata: {metadata['workflow_id']}")
                            return {
                                "type": "workflow",
                                "id": metadata['workflow_id'],
                                "name": metadata.get('workflow_name')
                            }
                        
                        # Check in entities dict
                        if entities.get(f"{entity_type}_id"):
                            logger.info(f"Found {entity_type}_id in entities: {entities[f'{entity_type}_id']}")
                            return {
                                "type": entity_type,
                                "id": entities[f"{entity_type}_id"],
                                "name": entities.get(f"{entity_type}_name")
                            }
                            
                    # If no specific type requested, return the first significant entity found
                    else:
                        if metadata.get('workflow_id'):
                            return {
                                "type": "workflow",
                                "id": metadata['workflow_id'],
                                "name": metadata.get('workflow_name')
                            }
                        if entities.get('workflow_id'):
                             return {
                                "type": "workflow",
                                "id": entities['workflow_id'],
                                "name": entities.get('workflow_name')
                            }
                            
                except Exception as e:
                    logger.warning(f"Error parsing metadata in resolution: {e}")
                    continue
            
            logger.info("Context resolution: No matching entity found")
            return None
            
        except Exception as e:
            logger.error(f"Error resolving reference: {e}")
            return None

    async def get_recent_context(self, session_id: str, workspace_id: Optional[str] = None, limit: int = 5) -> str:
        """
        Get a text summary of recent context to feed into the LLM.
        """
        from core.lancedb_handler import get_chat_history_manager
        chat_history = get_chat_history_manager(workspace_id)
        messages = chat_history.get_session_history(session_id, limit=limit)
        if not messages:
            return ""

        # Format messages as conversation
        formatted = []
        for msg in messages:
            role = msg.get("role", "unknown")
            content = msg.get("text", "")
            # Truncate long content
            if len(content) > 200:
                content = content[:197] + "..."
            formatted.append(f"{role.capitalize()}: {content}")

        return "\n".join(formatted)

    async def store_workflow_context(self, session_id: str, user_id: str, workspace_id: str, workflow_id: str, workflow_name: str, execution_id: str = None, status: str = "started") -> bool:
        """
        Store workflow execution context in chat memory.
        """
        from core.lancedb_handler import get_chat_history_manager
        chat_history = get_chat_history_manager(workspace_id)
        content = f"Workflow '{workflow_name}' ({workflow_id}) {status}."
        if execution_id:
            content += f" Execution ID: {execution_id}"
        metadata = {
            "workflow_id": workflow_id,
            "workflow_name": workflow_name,
            "execution_id": execution_id,
            "status": status,
            "type": "workflow_execution"
        }
        return chat_history.save_message(
            session_id=session_id,
            user_id=user_id,
            role="system",
            content=content,
            metadata=metadata
        )

# Helper for backward compatibility or direct instantiation
def get_chat_context_manager(workspace_id: Optional[str] = None) -> ChatContextManager:
    from core.lancedb_handler import get_chat_context_manager as get_mgr
    return get_mgr(workspace_id)
