"""
ATOM Chat Interface - Slack Integration
Enhanced chat interface with Slack integration, command handling, and context management
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Callable, AsyncGenerator
from dataclasses import dataclass, asdict
import httpx
import re

# Import ATOM components
try:
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from slack_service_unified import SlackUnifiedService
    from slack_workflow_automation import slack_workflow_automation
except ImportError:
    # Mock components for development
    AtomMemoryService = None
    AtomSearchService = None
    SlackUnifiedService = None
    slack_workflow_automation = None

logger = logging.getLogger(__name__)

@dataclass
class ChatMessage:
    """Chat message structure"""
    id: str
    user_id: str
    user_name: str
    message: str
    timestamp: datetime
    channel: str
    context: Dict[str, Any]
    source: str  # 'user', 'agent', 'slack'
    metadata: Dict[str, Any] = None

@dataclass
class ChatContext:
    """Chat context for conversation tracking"""
    conversation_id: str
    user_id: str
    messages: List[ChatMessage]
    slack_workspace_id: Optional[str] = None
    slack_channel_id: Optional[str] = None
    current_topic: Optional[str] = None
    intents: List[str] = None
    entities: Dict[str, Any] = None

@dataclass
class SlackCommand:
    """Slack command structure"""
    trigger: str
    pattern: str
    handler: Callable
    description: str
    requires_slack: bool = False
    permission_level: str = 'user'

class AtomChatInterface:
    """ATOM Chat interface with Slack integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.memory_service = AtomMemoryService() if AtomMemoryService else None
        self.search_service = AtomSearchService() if AtomSearchService else None
        self.slack_service = SlackUnifiedService(config.get('slack', {})) if SlackUnifiedService else None
        
        # Conversation contexts
        self.contexts: Dict[str, ChatContext] = {}
        
        # Command handlers
        self.commands: Dict[str, SlackCommand] = {}
        
        # Message callbacks
        self.message_callbacks: List[Callable[[ChatMessage], None]] = []
        
        # Slack integration status
        self.slack_connected = False
        self.slack_workspaces: List[Dict[str, Any]] = []
        self.slack_channels: Dict[str, Dict[str, Any]] = {}
        
        # Initialize commands
        self._register_commands()
        
        logger.info("ATOM Chat Interface initialized")
    
    def _register_commands(self):
        """Register chat commands"""
        
        # Slack integration commands
        self.commands['slack-connect'] = SlackCommand(
            trigger='slack-connect',
            pattern=r'/slack-connect',
            handler=self._handle_slack_connect,
            description='Connect to Slack workspace',
            requires_slack=False
        )
        
        self.commands['slack-channels'] = SlackCommand(
            trigger='slack-channels',
            pattern=r'/slack-channels(?:\s+(.+))?',
            handler=self._handle_slack_channels,
            description='List or switch Slack channels',
            requires_slack=True
        )
        
        self.commands['slack-send'] = SlackCommand(
            trigger='slack-send',
            pattern=r'/slack-send\s+(?:#(\w+)\s+)?(.+)',
            handler=self._handle_slack_send,
            description='Send message to Slack channel',
            requires_slack=True
        )
        
        self.commands['slack-search'] = SlackCommand(
            trigger='slack-search',
            pattern=r'/slack-search\s+(.+)',
            handler=self._handle_slack_search,
            description='Search Slack messages',
            requires_slack=True
        )
        
        self.commands['slack-workflows'] = SlackCommand(
            trigger='slack-workflows',
            pattern=r'/slack-workflows(?:\s+(list|create|run))\s*(.*)?',
            handler=self._handle_slack_workflows,
            description='Manage Slack workflows',
            requires_slack=True
        )
        
        # Memory and search commands
        self.commands['remember'] = SlackCommand(
            trigger='remember',
            pattern=r'/remember\s+(.+)',
            handler=self._handle_remember,
            description='Store information in memory',
            requires_slack=False
        )
        
        self.commands['recall'] = SlackCommand(
            trigger='recall',
            pattern=r'/recall(?:\s+(.+))?',
            handler=self._handle_recall,
            description='Retrieve information from memory',
            requires_slack=False
        )
        
        self.commands['search'] = SlackCommand(
            trigger='search',
            pattern=r'/search\s+(.+)',
            handler=self._handle_search,
            description='Search all indexed content',
            requires_slack=False
        )
        
        # General commands
        self.commands['help'] = SlackCommand(
            trigger='help',
            pattern=r'/help(?:\s+(.+))?',
            handler=self._handle_help,
            description='Show available commands',
            requires_slack=False
        )
        
        self.commands['context'] = SlackCommand(
            trigger='context',
            pattern=r'/context(?:\s+(show|clear|set)\s*(.*))?',
            handler=self._handle_context,
            description='Manage conversation context',
            requires_slack=False
        )
    
    async def process_message(self, message: str, user_id: str, user_name: str,
                            source: str = 'user', context: Dict[str, Any] = None) -> str:
        """Process incoming message and generate response"""
        try:
            # Get or create conversation context
            conversation_id = context.get('conversation_id', f"conv_{user_id}_{int(datetime.utcnow().timestamp())}")
            chat_context = self._get_context(conversation_id, user_id)
            
            # Create chat message
            chat_message = ChatMessage(
                id=f"msg_{int(datetime.utcnow().timestamp())}",
                user_id=user_id,
                user_name=user_name,
                message=message,
                timestamp=datetime.utcnow(),
                channel=context.get('channel', 'default'),
                context=context or {},
                source=source
            )
            
            # Add to context
            chat_context.messages.append(chat_message)
            
            # Process commands
            if message.startswith('/'):
                response = await self._process_command(chat_message)
            else:
                # Process as regular message with AI
                response = await self._process_regular_message(chat_message)
            
            # Update context in memory
            await self._save_context(chat_context)
            
            # Notify callbacks
            await self._notify_callbacks(chat_message)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing message: {e}")
            return f"Sorry, I encountered an error while processing your message: {str(e)}"
    
    async def _process_command(self, message: ChatMessage) -> str:
        """Process slash commands"""
        content = message.message
        user_permissions = self._get_user_permissions(message.user_id)
        
        # Find matching command
        for trigger, command in self.commands.items():
            if content.startswith(f"/{trigger} ") or content == f"/{trigger}":
                # Check permissions
                if not self._check_permissions(user_permissions, command.permission_level):
                    return "You don't have permission to use this command."
                
                # Check Slack requirement
                if command.requires_slack and not self.slack_connected:
                    return "This command requires Slack to be connected. Use `/slack-connect` first."
                
                # Execute command
                try:
                    match = re.match(command.pattern, content)
                    if match:
                        result = await command.handler(message, *match.groups())
                        return result
                    else:
                        return f"Invalid command syntax. Usage: {command.description}"
                except Exception as e:
                    logger.error(f"Error executing command {trigger}: {e}")
                    return f"Error executing command: {str(e)}"
        
        return "Unknown command. Use `/help` to see available commands."
    
    async def _process_regular_message(self, message: ChatMessage) -> str:
        """Process regular message with AI"""
        try:
            # Extract intents and entities
            intents, entities = await self._extract_intents_entities(message.message)
            
            # Update context
            if message.context.get('conversation_id'):
                chat_context = self._get_context(
                    message.context['conversation_id'],
                    message.user_id
                )
                chat_context.intents.extend(intents)
                chat_context.entities.update(entities)
            
            # Generate AI response
            response = await self._generate_ai_response(message, intents, entities)
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing regular message: {e}")
            return "I understand your message, but I'm having trouble generating a response right now."
    
    async def _handle_slack_connect(self, message: ChatMessage, workspace_id: str = None) -> str:
        """Handle Slack connection"""
        try:
            if not self.slack_service:
                return "Slack service is not available."
            
            if workspace_id:
                # Connect to specific workspace
                result = await self.slack_service.test_connection(workspace_id)
                if result.get('connected'):
                    self.slack_connected = True
                    return f"Successfully connected to Slack workspace: {result.get('team', 'Unknown')}"
                else:
                    return f"Failed to connect to workspace: {result.get('error', 'Unknown error')}"
            else:
                # List available workspaces
                workspaces = await self.slack_service.list_workspaces(message.user_id)
                if workspaces:
                    workspace_list = "\n".join([
                        f"• {ws.name} ({ws.domain}.slack.com) - ID: {ws.id}"
                        for ws in workspaces
                    ])
                    return f"Available workspaces:\n{workspace_list}\n\nUse `/slack-connect <workspace_id>` to connect."
                else:
                    return "No workspaces available. Please connect your Slack account first."
        
        except Exception as e:
            logger.error(f"Error connecting to Slack: {e}")
            return f"Error connecting to Slack: {str(e)}"
    
    async def _handle_slack_channels(self, message: ChatMessage, channel_name: str = None) -> str:
        """Handle Slack channel listing/switching"""
        try:
            if not self.slack_connected:
                return "Please connect to Slack first using `/slack-connect`."
            
            workspace_id = self._get_context_channel_workspace(message.context)
            
            if channel_name:
                # Switch to specific channel
                channels = await self.slack_service.list_channels(workspace_id, message.user_id)
                target_channel = next((c for c in channels if c['name'] == channel_name), None)
                
                if target_channel:
                    # Update context
                    if message.context.get('conversation_id'):
                        chat_context = self._get_context(
                            message.context['conversation_id'],
                            message.user_id
                        )
                        chat_context.slack_channel_id = target_channel['id']
                    
                    return f"Switched to Slack channel: #{channel_name}"
                else:
                    return f"Channel #{channel_name} not found."
            else:
                # List channels
                channels = await self.slack_service.list_channels(workspace_id, message.user_id)
                channel_list = "\n".join([
                    f"• #{c['name']} ({c['num_members']} members) - ID: {c['id']}"
                    for c in channels[:20]  # Limit to first 20
                ])
                return f"Available channels:\n{channel_list}"
        
        except Exception as e:
            logger.error(f"Error handling Slack channels: {e}")
            return f"Error listing channels: {str(e)}"
    
    async def _handle_slack_send(self, message: ChatMessage, channel: str = None, content: str = None) -> str:
        """Handle sending message to Slack"""
        try:
            if not self.slack_connected:
                return "Please connect to Slack first using `/slack-connect`."
            
            workspace_id = self._get_context_channel_workspace(message.context)
            
            # Use current context channel if not specified
            if not channel:
                chat_context = self._get_context(
                    message.context.get('conversation_id'),
                    message.user_id
                )
                channel_id = chat_context.slack_channel_id
            else:
                # Find channel by name
                channels = await self.slack_service.list_channels(workspace_id, message.user_id)
                target_channel = next((c for c in channels if c['name'] == channel), None)
                channel_id = target_channel['id'] if target_channel else None
            
            if not channel_id:
                return "Channel not found. Use `/slack-channels` to see available channels."
            
            # Send message
            result = await self.slack_service.post_message(workspace_id, channel_id, content)
            
            if result.get('ok'):
                return f"Message sent to Slack channel #{channel or 'unknown'}."
            else:
                return f"Failed to send message: {result.get('error', 'Unknown error')}"
        
        except Exception as e:
            logger.error(f"Error sending Slack message: {e}")
            return f"Error sending message: {str(e)}"
    
    async def _handle_slack_search(self, message: ChatMessage, query: str) -> str:
        """Handle Slack message search"""
        try:
            if not self.slack_connected:
                return "Please connect to Slack first using `/slack-connect`."
            
            workspace_id = self._get_context_channel_workspace(message.context)
            
            # Search messages
            result = await self.slack_service.search_messages(workspace_id, query)
            
            if result.get('ok') and result.get('messages'):
                messages = result['messages'][:5]  # Limit to 5 results
                search_results = "\n".join([
                    f"• From {msg.get('user_name', 'Unknown')} in #{msg.get('channel_name', 'unknown')}:\n"
                    f"  {msg.get('text', 'No text')[:100]}...\n"
                    f"  ({msg.get('ts', 'Unknown')})"
                    for msg in messages
                ])
                return f"Found {len(result['messages'])} results:\n{search_results}"
            else:
                return f"No messages found for query: {query}"
        
        except Exception as e:
            logger.error(f"Error searching Slack: {e}")
            return f"Error searching Slack: {str(e)}"
    
    async def _handle_slack_workflows(self, message: ChatMessage, action: str = 'list', params: str = '') -> str:
        """Handle Slack workflow management"""
        try:
            if action == 'list':
                workflows = slack_workflow_automation.list_workspaces() if slack_workflow_automation else []
                if workflows:
                    workflow_list = "\n".join([
                        f"• {w.name} - {w.description} (Status: {'Active' if w.active else 'Inactive'})"
                        for w in workflows
                    ])
                    return f"Available workflows:\n{workflow_list}"
                else:
                    return "No workflows configured."
            
            elif action == 'run':
                if not params:
                    return "Please specify a workflow ID or name to run."
                
                # Find workflow
                workflows = slack_workflow_automation.list_workspaces() if slack_workflow_automation else []
                workflow = next((w for w in workflows if w.name == params or w.id == params), None)
                
                if workflow:
                    # Execute workflow
                    execution = await slack_workflow_automation.execute_workflow(
                        workflow.id,
                        {
                            'user_id': message.user_id,
                            'source': 'chat_interface'
                        }
                    )
                    return f"Workflow '{workflow.name}' started. Execution ID: {execution.id}"
                else:
                    return f"Workflow '{params}' not found."
            
            else:
                return "Available workflow actions: list, run"
        
        except Exception as e:
            logger.error(f"Error handling Slack workflows: {e}")
            return f"Error with workflows: {str(e)}"
    
    async def _handle_remember(self, message: ChatMessage, content: str) -> str:
        """Handle remembering information"""
        try:
            if not self.memory_service:
                return "Memory service is not available."
            
            # Store in memory
            memory_data = {
                'type': 'user_memory',
                'user_id': message.user_id,
                'content': content,
                'timestamp': datetime.utcnow().isoformat(),
                'context': message.context
            }
            
            await self.memory_service.store(memory_data)
            return f"I'll remember: {content}"
        
        except Exception as e:
            logger.error(f"Error storing in memory: {e}")
            return f"Error storing information: {str(e)}"
    
    async def _handle_recall(self, message: ChatMessage, query: str = None) -> str:
        """Handle recalling information"""
        try:
            if not self.memory_service:
                return "Memory service is not available."
            
            if query:
                # Search memory
                results = await self.memory_service.search(query, user_id=message.user_id)
                if results:
                    memories = "\n".join([
                        f"• {result['content']} ({result['timestamp']})"
                        for result in results[:5]
                    ])
                    return f"Found memories:\n{memories}"
                else:
                    return f"No memories found for: {query}"
            else:
                # Get recent memories
                memories = await self.memory_service.get_recent(user_id=message.user_id, limit=5)
                if memories:
                    memory_list = "\n".join([
                        f"• {mem['content']} ({mem['timestamp']})"
                        for mem in memories
                    ])
                    return f"Recent memories:\n{memory_list}"
                else:
                    return "No memories found."
        
        except Exception as e:
            logger.error(f"Error recalling from memory: {e}")
            return f"Error recalling information: {str(e)}"
    
    async def _handle_search(self, message: ChatMessage, query: str) -> str:
        """Handle searching all content"""
        try:
            if not self.search_service:
                return "Search service is not available."
            
            # Search all indexed content
            results = await self.search_service.search(query, user_id=message.user_id)
            
            if results:
                search_results = "\n".join([
                    f"• {result['title'] or 'Untitled'} ({result['source']}):\n"
                    f"  {result['snippet'] or result['text'][:100]}...\n"
                    f"  ({result['timestamp']})"
                    for result in results[:5]
                ])
                return f"Found {len(results)} results:\n{search_results}"
            else:
                return f"No results found for: {query}"
        
        except Exception as e:
            logger.error(f"Error searching: {e}")
            return f"Error searching: {str(e)}"
    
    async def _handle_help(self, message: ChatMessage, command: str = None) -> str:
        """Handle help command"""
        if command:
            # Show specific command help
            if command in self.commands:
                cmd = self.commands[command]
                return f"Command: /{cmd.trigger}\nDescription: {cmd.description}\nRequires Slack: {cmd.requires_slack}"
            else:
                return f"Unknown command: {command}. Use `/help` to see all commands."
        else:
            # Show all commands
            user_permissions = self._get_user_permissions(message.user_id)
            available_commands = [
                f"• /{trigger} - {cmd.description}"
                for trigger, cmd in self.commands.items()
                if self._check_permissions(user_permissions, cmd.permission_level)
            ]
            
            help_text = "Available commands:\n" + "\n".join(available_commands)
            return help_text
    
    async def _handle_context(self, message: ChatMessage, action: str = 'show', target: str = '') -> str:
        """Handle context management"""
        if not message.context.get('conversation_id'):
            return "No conversation context available."
        
        chat_context = self._get_context(
            message.context['conversation_id'],
            message.user_id
        )
        
        if action == 'show':
            context_info = f"""Current Context:
• Conversation ID: {chat_context.conversation_id}
• Messages: {len(chat_context.messages)}
• Slack Workspace: {chat_context.slack_workspace_id or 'Not set'}
• Slack Channel: {chat_context.slack_channel_id or 'Not set'}
• Current Topic: {chat_context.current_topic or 'None'}
• Intents: {', '.join(chat_context.intents) if chat_context.intents else 'None'}
• Entities: {json.dumps(chat_context.entities) if chat_context.entities else 'None'}"""
            return context_info
        
        elif action == 'clear':
            # Clear context
            chat_context.messages = []
            chat_context.intents = []
            chat_context.entities = {}
            await self._save_context(chat_context)
            return "Context cleared."
        
        elif action == 'set' and target:
            # Set topic or entity
            chat_context.current_topic = target
            await self._save_context(chat_context)
            return f"Context topic set to: {target}"
        
        else:
            return "Available context actions: show, clear, set <topic>"
    
    def _get_context(self, conversation_id: str, user_id: str) -> ChatContext:
        """Get or create conversation context"""
        if conversation_id not in self.contexts:
            self.contexts[conversation_id] = ChatContext(
                conversation_id=conversation_id,
                user_id=user_id,
                messages=[],
                intents=[],
                entities={}
            )
        
        return self.contexts[conversation_id]
    
    async def _save_context(self, context: ChatContext):
        """Save context to memory"""
        if self.memory_service:
            try:
                context_data = {
                    'type': 'conversation_context',
                    'conversation_id': context.conversation_id,
                    'data': asdict(context),
                    'timestamp': datetime.utcnow().isoformat()
                }
                await self.memory_service.store(context_data)
            except Exception as e:
                logger.error(f"Error saving context: {e}")
    
    async def _extract_intents_entities(self, message: str) -> tuple:
        """Extract intents and entities from message"""
        # This would integrate with your NLP service
        # For now, return basic extracted information
        intents = []
        entities = {}
        
        # Extract Slack-related intents
        if any(word in message.lower() for word in ['send', 'post', 'share']):
            intents.append('send_message')
        
        if any(word in message.lower() for word in ['find', 'search', 'look']):
            intents.append('search')
        
        if any(word in message.lower() for word in ['remember', 'save', 'store']):
            intents.append('remember')
        
        # Extract channel entities
        channel_match = re.search(r'#(\w+)', message)
        if channel_match:
            entities['channel'] = channel_match.group(1)
        
        return intents, entities
    
    async def _generate_ai_response(self, message: ChatMessage, intents: List[str], entities: Dict[str, Any]) -> str:
        """Generate AI response based on context"""
        # This would integrate with your AI/LLM service
        # For now, provide basic contextual responses
        
        context = message.context
        
        # Check for Slack context
        if context.get('slack_channel_id'):
            responses = [
                "I can help you manage your Slack integration. Try `/slack-channels` to see available channels.",
                "Need to send a message? Use `/slack-send #channel <message>`.",
                "Looking for something? Try `/slack-search <query>`."
            ]
            return responses[hash(message.message) % len(responses)]
        
        # General responses
        if 'search' in intents:
            return "I can search across all your connected services. Try `/search <query>` or `/slack-search <query>` for Slack-specific search."
        
        if 'send_message' in intents:
            return "I can help you send messages. Use `/slack-send #channel <message>` to send to Slack."
        
        # Context-aware response
        if len(self._get_context(context.get('conversation_id'), message.user_id).messages) > 5:
            return "I've been tracking our conversation. Is there anything specific you'd like me to help with?"
        
        return "I'm here to help! You can ask me questions, manage your Slack integration, or use `/help` to see all available commands."
    
    def _get_user_permissions(self, user_id: str) -> List[str]:
        """Get user permissions"""
        # This would integrate with your user management system
        # For now, return basic permissions
        return ['user']
    
    def _check_permissions(self, user_permissions: List[str], required_level: str) -> bool:
        """Check if user has required permissions"""
        permission_levels = {
            'user': 1,
            'admin': 2,
            'super_admin': 3
        }
        
        user_level = max([permission_levels.get(perm, 0) for perm in user_permissions])
        required_level_num = permission_levels.get(required_level, 1)
        
        return user_level >= required_level_num
    
    def _get_context_channel_workspace(self, context: Dict[str, Any]) -> Optional[str]:
        """Get workspace ID from context"""
        if context and context.get('conversation_id'):
            chat_context = self._get_context(context['conversation_id'], context.get('user_id', ''))
            return chat_context.slack_workspace_id
        return None
    
    async def _notify_callbacks(self, message: ChatMessage):
        """Notify registered message callbacks"""
        for callback in self.message_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(message)
                else:
                    callback(message)
            except Exception as e:
                logger.error(f"Error in message callback: {e}")
    
    def add_message_callback(self, callback: Callable[[ChatMessage], None]):
        """Add message callback"""
        self.message_callbacks.append(callback)
    
    def remove_message_callback(self, callback: Callable[[ChatMessage], None]):
        """Remove message callback"""
        if callback in self.message_callbacks:
            self.message_callbacks.remove(callback)
    
    def get_conversation_history(self, conversation_id: str) -> List[ChatMessage]:
        """Get conversation history"""
        context = self.contexts.get(conversation_id)
        return context.messages if context else []
    
    async def index_slack_content(self):
        """Index Slack content for search"""
        if not self.slack_connected or not self.search_service:
            return
        
        try:
            # Index all available Slack content
            for workspace in self.slack_workspaces:
                # Get channels
                channels = await self.slack_service.list_channels(workspace['id'], 'system')
                
                for channel in channels:
                    # Get messages
                    messages = await self.slack_service.get_channel_history(
                        workspace['id'], channel['id'], limit=1000
                    )
                    
                    # Index messages
                    for msg in messages:
                        content_data = {
                            'source': 'slack',
                            'workspace_id': workspace['id'],
                            'channel_id': channel['id'],
                            'message_id': msg['ts'],
                            'text': msg.get('text', ''),
                            'user': msg.get('user'),
                            'timestamp': msg['ts'],
                            'metadata': {
                                'reactions': msg.get('reactions', []),
                                'files': msg.get('files', []),
                                'thread_ts': msg.get('thread_ts')
                            }
                        }
                        
                        await self.search_service.index(content_data)
        
        except Exception as e:
            logger.error(f"Error indexing Slack content: {e}")
    
    async def sync_with_slack(self):
        """Sync with Slack workspaces"""
        try:
            if self.slack_service:
                # Refresh workspace list
                self.slack_workspaces = await self.slack_service.list_workspaces('system')
                self.slack_connected = len(self.slack_workspaces) > 0
                
                # Index content for search
                await self.index_slack_content()
        
        except Exception as e:
            logger.error(f"Error syncing with Slack: {e}")

# Global chat interface instance
atom_chat_interface = AtomChatInterface({
    'slack': {
        'client_id': os.getenv('SLACK_CLIENT_ID'),
        'client_secret': os.getenv('SLACK_CLIENT_SECRET'),
        'signing_secret': os.getenv('SLACK_SIGNING_SECRET')
    }
})