"""
ATOM WhatsApp Integration
Advanced WhatsApp platform integration with enterprise features and automation
"""

import os
import json
import logging
import asyncio
import time
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import aiohttp
from collections import defaultdict, Counter
import pandas as pd
import numpy as np

# Import existing ATOM services
try:
    from atom_enterprise_security_service import atom_enterprise_security_service, SecurityLevel, ComplianceStandard
    from atom_enterprise_unified_service import atom_enterprise_unified_service, WorkflowSecurityLevel
    from atom_workflow_automation_service import atom_workflow_automation_service, AutomationPriority, AutomationStatus
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import AtomWorkflowService
    from atom_ingestion_pipeline import AtomIngestionPipeline
    from ai_enhanced_service import ai_enhanced_service, AIRequest, AIResponse, AITaskType, AIModelType, AIServiceType
    from atom_ai_integration import atom_ai_integration
    from atom_slack_integration import atom_slack_integration
    from atom_teams_integration import atom_teams_integration
    from atom_google_chat_integration import atom_google_chat_integration
    from atom_discord_integration import atom_discord_integration
    from atom_telegram_integration import atom_telegram_integration
except ImportError as e:
    logging.warning(f"Enterprise services not available: {e}")

# Configure logging
logger = logging.getLogger(__name__)

class WhatsAppMessageType(Enum):
    """WhatsApp message types"""
    TEXT = "text"
    IMAGE = "image"
    VIDEO = "video"
    AUDIO = "audio"
    VOICE = "voice"
    DOCUMENT = "document"
    STICKER = "sticker"
    LOCATION = "location"
    CONTACT = "contact"
    INTERACTIVE = "interactive"
    TEMPLATE = "template"
    REACTION = "reaction"

class WhatsAppChatType(Enum):
    """WhatsApp chat types"""
    PRIVATE = "private"
    GROUP = "group"
    BROADCAST = "broadcast"

class WhatsAppCommandType(Enum):
    """WhatsApp command types"""
    START = "start"
    HELP = "help"
    STATUS = "status"
    SEARCH = "search"
    WORKFLOW = "workflow"
    AUTOMATE = "automate"
    SECURITY = "security"
    COMPLIANCE = "compliance"
    ANALYTICS = "analytics"
    MONITOR = "monitor"
    REPORT = "report"
    ADMIN = "admin"

@dataclass
class WhatsAppUser:
    """WhatsApp user data model"""
    user_id: str
    phone_number: str
    name: str
    profile_picture: Optional[str]
    is_business: bool
    is_verified: bool
    is_active: bool
    permissions: List[str]
    security_level: str
    created_at: datetime
    last_active: datetime
    metadata: Dict[str, Any]

@dataclass
class WhatsAppChat:
    """WhatsApp chat data model"""
    chat_id: str
    chat_type: WhatsAppChatType
    name: Optional[str]
    description: Optional[str]
    profile_picture: Optional[str]
    participants: List[str]
    admin_participants: List[str]
    permissions: Dict[str, Any]
    security_level: str
    is_active: bool
    member_count: int
    created_at: datetime
    last_message: datetime
    metadata: Dict[str, Any]

@dataclass
class WhatsAppMessage:
    """WhatsApp message data model"""
    message_id: str
    chat_id: str
    user_id: str
    message_type: WhatsAppMessageType
    content: str
    media_path: Optional[str]
    reply_to_message_id: Optional[str]
    forward_from: Optional[str]
    edit_date: Optional[datetime]
    timestamp: datetime
    views: int
    reactions: List[Dict[str, Any]]
    security_flags: Dict[str, Any]
    metadata: Dict[str, Any]

class AtomWhatsAppIntegration:
    """Advanced WhatsApp integration with enterprise features"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = config.get('database')
        self.cache = config.get('cache')
        
        # WhatsApp configuration
        self.whatsapp_config = {
            'phone_number_id': config.get('phone_number_id') or os.getenv('WHATSAPP_PHONE_NUMBER_ID'),
            'business_account_id': config.get('business_account_id') or os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID'),
            'access_token': config.get('access_token') or os.getenv('WHATSAPP_ACCESS_TOKEN'),
            'webhook_url': config.get('webhook_url') or os.getenv('WHATSAPP_WEBHOOK_URL'),
            'webhook_secret': config.get('webhook_secret') or os.getenv('WHATSAPP_WEBHOOK_SECRET'),
            'admin_phone_numbers': config.get('admin_phone_numbers', []),
            'allowed_chat_types': config.get('allowed_chat_types', ['private', 'group']),
            'max_message_length': config.get('max_message_length', 4000),
            'enable_enterprise_features': config.get('enable_enterprise_features', True),
            'security_level': config.get('security_level', 'standard'),
            'compliance_standards': config.get('compliance_standards', ['GDPR', 'SOC2', 'ISO27001']),
            'api_version': config.get('api_version', 'v18.0'),
            'api_base_url': config.get('api_base_url', 'https://graph.facebook.com')
        }
        
        # Integration state
        self.is_initialized = False
        self.active_chats: Dict[str, WhatsAppChat] = {}
        self.active_users: Dict[str, WhatsAppUser] = {}
        self.message_history: Dict[str, List[WhatsAppMessage]] = {}
        self.command_handlers: Dict[str, Callable] = {}
        self.message_handlers: List[Callable] = []
        
        # Enterprise integration
        self.enterprise_security = config.get('security_service') or atom_enterprise_security_service
        self.enterprise_automation = config.get('automation_service') or atom_workflow_automation_service
        self.ai_service = config.get('ai_service') or ai_enhanced_service
        
        # Analytics and monitoring
        self.analytics_metrics = {
            'total_messages': 0,
            'total_chats': 0,
            'total_users': 0,
            'commands_executed': 0,
            'automations_triggered': 0,
            'security_incidents': 0,
            'compliance_checks': 0,
            'ai_requests': 0,
            'message_types': defaultdict(int),
            'chat_types': defaultdict(int),
            'active_chats': 0,
            'active_users': 0
        }
        
        # Security and compliance
        self.security_policies = {}
        self.compliance_rules = {}
        self.automation_triggers = {}
        self.message_filters = []
        
        # Performance metrics
        self.performance_metrics = {
            'message_processing_time': 0.0,
            'command_response_time': 0.0,
            'ai_processing_time': 0.0,
            'security_check_time': 0.0,
            'compliance_check_time': 0.0,
            'automation_execution_time': 0.0,
            'webhook_response_time': 0.0
        }
        
        # HTTP session for API calls
        self.http_session = httpx.AsyncClient(
            timeout=30.0,
            headers={
                'Authorization': f'Bearer {self.whatsapp_config["access_token"]}',
                'Content-Type': 'application/json'
            }
        )
        
        logger.info("WhatsApp Integration initialized")
    
    async def initialize(self) -> bool:
        """Initialize WhatsApp integration"""
        try:
            if not self.whatsapp_config['access_token']:
                logger.error("WhatsApp access token not provided")
                return False
            
            # Verify WhatsApp Business API connection
            await self._verify_api_connection()
            
            # Setup webhook
            if self.whatsapp_config['webhook_url']:
                await self._setup_webhook()
            
            # Setup enterprise features
            if self.whatsapp_config['enable_enterprise_features']:
                await self._setup_enterprise_features()
            
            # Setup security and compliance
            await self._setup_security_and_compliance()
            
            # Setup automation
            await self._setup_automation()
            
            # Setup monitoring
            await self._setup_monitoring()
            
            # Load existing data
            await self._load_existing_data()
            
            self.is_initialized = True
            logger.info("WhatsApp Integration initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing WhatsApp integration: {e}")
            return False
    
    async def get_intelligent_workspaces(self, user_id: str) -> List[Dict[str, Any]]:
        """Get intelligent workspaces for user"""
        try:
            workspaces = []
            
            for chat_id, chat in self.active_chats.items():
                # Check if user has access to chat
                if chat.is_active and user_id in chat.participants:
                    workspace = {
                        'id': chat.chat_id,
                        'name': chat.name or f"Chat {chat.chat_id}",
                        'type': chat.chat_type.value,
                        'member_count': chat.member_count,
                        'description': chat.description,
                        'last_activity': chat.last_message.isoformat(),
                        'security_level': chat.security_level,
                        'permissions': chat.permissions,
                        'participant_count': len(chat.participants),
                        'admin_count': len(chat.admin_participants),
                        'is_group': chat.chat_type == WhatsAppChatType.GROUP,
                        'platform': 'whatsapp'
                    }
                    workspaces.append(workspace)
            
            # Sort by last activity
            workspaces.sort(key=lambda x: x['last_activity'], reverse=True)
            
            return workspaces
            
        except Exception as e:
            logger.error(f"Error getting intelligent workspaces: {e}")
            return []
    
    async def get_intelligent_channels(self, workspace_id: str, user_id: str) -> List[Dict[str, Any]]:
        """Get intelligent channels for workspace"""
        try:
            channels = []
            chat = self.active_chats.get(workspace_id)
            
            if chat and user_id in chat.participants:
                # For WhatsApp, workspace is chat itself
                channel = {
                    'id': chat.chat_id,
                    'name': chat.name or f"Chat {chat.chat_id}",
                    'type': chat.chat_type.value,
                    'member_count': chat.member_count,
                    'description': chat.description,
                    'security_level': chat.security_level,
                    'permissions': chat.permissions,
                    'is_active': chat.is_active,
                    'participants': chat.participants,
                    'admin_participants': chat.admin_participants,
                    'last_activity': chat.last_message.isoformat(),
                    'platform': 'whatsapp',
                    'is_private': chat.chat_type == WhatsAppChatType.PRIVATE,
                    'is_group': chat.chat_type == WhatsAppChatType.GROUP
                }
                channels.append(channel)
            
            return channels
            
        except Exception as e:
            logger.error(f"Error getting intelligent channels: {e}")
            return []
    
    async def send_intelligent_message(self, channel_id: str, message: str, metadata: Dict[str, Any] = None) -> Dict[str, Any]:
        """Send intelligent message"""
        try:
            # Send message via WhatsApp API
            api_url = f"{self.whatsapp_config['api_base_url']}/{self.whatsapp_config['api_version']}/{self.whatsapp_config['phone_number_id']}/messages"
            
            message_data = {
                'messaging_product': 'whatsapp',
                'recipient_type': 'individual',
                'to': channel_id,
                'type': 'text',
                'text': {
                    'body': message
                }
            }
            
            response = await self.http_session.post(api_url, json=message_data)
            
            if response.status_code == 200:
                result = {
                    'success': True,
                    'channel_id': channel_id,
                    'message': message,
                    'timestamp': datetime.utcnow().isoformat(),
                    'platform': 'whatsapp',
                    'metadata': metadata or {},
                    'message_id': response.json().get('messages', [{}])[0].get('id')
                }
                
                # Log message
                if self.whatsapp_config['enable_enterprise_features']:
                    await self._log_message_event('message_sent', channel_id, result)
                
                return result
            else:
                error_response = response.json()
                return {
                    'success': False,
                    'error': error_response.get('error', {}).get('message', 'Unknown error'),
                    'platform': 'whatsapp'
                }
            
        except Exception as e:
            logger.error(f"Error sending intelligent message: {e}")
            return {
                'success': False,
                'error': str(e),
                'platform': 'whatsapp'
            }
    
    async def perform_intelligent_search(self, query: str, user_id: str, workspace_id: str = None) -> List[Dict[str, Any]]:
        """Perform intelligent search"""
        try:
            search_results = []
            
            # Search in message history
            for chat_id, messages in self.message_history.items():
                if workspace_id and chat_id != workspace_id:
                    continue
                
                for message in messages:
                    if query.lower() in message.content.lower():
                        result = {
                            'id': message.message_id,
                            'type': 'whatsapp_message',
                            'title': f"Message {message.message_id}",
                            'snippet': message.content[:100] + "..." if len(message.content) > 100 else message.content,
                            'content': message.content,
                            'channel_id': message.chat_id,
                            'user_id': message.user_id,
                            'timestamp': message.timestamp.isoformat(),
                            'message_type': message.message_type.value,
                            'platform': 'whatsapp',
                            'relevance_score': self._calculate_relevance_score(query, message.content)
                        }
                        search_results.append(result)
            
            # Sort by relevance score
            search_results.sort(key=lambda x: x['relevance_score'], reverse=True)
            
            # AI-enhanced search
            if self.ai_service:
                ai_results = await self._perform_ai_search(query, workspace_id)
                search_results.extend(ai_results)
            
            return search_results[:20]  # Return top 20 results
            
        except Exception as e:
            logger.error(f"Error performing intelligent search: {e}")
            return []
    
    async def get_user_conversation_history(self, user_id: str, channel_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get user conversation history"""
        try:
            conversation_history = []
            messages = self.message_history.get(channel_id, [])
            
            # Filter by user and limit
            user_messages = [m for m in messages if m.user_id == user_id][-limit:]
            
            for message in user_messages:
                history_item = {
                    'id': message.message_id,
                    'content': message.content,
                    'message_type': message.message_type.value,
                    'timestamp': message.timestamp.isoformat(),
                    'channel_id': message.chat_id,
                    'platform': 'whatsapp',
                    'metadata': message.metadata
                }
                conversation_history.append(history_item)
            
            return conversation_history
            
        except Exception as e:
            logger.error(f"Error getting user conversation history: {e}")
            return []
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get WhatsApp service status"""
        try:
            return {
                'platform': 'whatsapp',
                'status': 'active' if self.is_initialized else 'inactive',
                'phone_number_id': self.whatsapp_config['phone_number_id'],
                'business_account_id': self.whatsapp_config['business_account_id'],
                'webhook_url': self.whatsapp_config['webhook_url'],
                'api_version': self.whatsapp_config['api_version'],
                'enterprise_features': self.whatsapp_config['enable_enterprise_features'],
                'security_level': self.whatsapp_config['security_level'],
                'compliance_standards': self.whatsapp_config['compliance_standards'],
                'total_messages': self.analytics_metrics['total_messages'],
                'total_chats': self.analytics_metrics['total_chats'],
                'total_users': self.analytics_metrics['total_users'],
                'commands_executed': self.analytics_metrics['commands_executed'],
                'automations_triggered': self.analytics_metrics['automations_triggered'],
                'security_incidents': self.analytics_metrics['security_incidents'],
                'compliance_checks': self.analytics_metrics['compliance_checks'],
                'ai_requests': self.analytics_metrics['ai_requests'],
                'active_chats': self.analytics_metrics['active_chats'],
                'active_users': self.analytics_metrics['active_users'],
                'performance_metrics': self.performance_metrics,
                'uptime': time.time() - (self._start_time if hasattr(self, '_start_time') else time.time())
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {'error': str(e), 'platform': 'whatsapp'}
    
    # Private helper methods
    async def _verify_api_connection(self):
        """Verify WhatsApp API connection"""
        try:
            api_url = f"{self.whatsapp_config['api_base_url']}/{self.whatsapp_config['api_version']}/me"
            response = await self.http_session.get(api_url)
            
            if response.status_code == 200:
                logger.info("WhatsApp API connection verified")
            else:
                logger.error(f"WhatsApp API connection failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error verifying API connection: {e}")
    
    async def _setup_webhook(self):
        """Setup webhook"""
        try:
            api_url = f"{self.whatsapp_config['api_base_url']}/{self.whatsapp_config['api_version']}/{self.whatsapp_config['phone_number_id']}/subscriptions"
            
            webhook_data = {
                'object': 'whatsapp_business_account',
                'callback_url': self.whatsapp_config['webhook_url'],
                'fields': ['messages', 'message_reactions'],
                'verify_token': self.whatsapp_config['webhook_secret']
            }
            
            response = await self.http_session.post(api_url, json=webhook_data)
            
            if response.status_code == 200:
                logger.info(f"WhatsApp webhook setup complete: {self.whatsapp_config['webhook_url']}")
            else:
                logger.error(f"WhatsApp webhook setup failed: {response.status_code}")
                
        except Exception as e:
            logger.error(f"Error setting up webhook: {e}")
    
    async def _setup_enterprise_features(self):
        """Setup enterprise features"""
        try:
            if not self.enterprise_security or not self.enterprise_automation:
                logger.warning("Enterprise services not available")
                return
            
            # Setup security policies
            await self._setup_security_policies()
            
            # Setup compliance rules
            await self._setup_compliance_rules()
            
            # Setup automation triggers
            await self._setup_automation_triggers()
            
            logger.info("Enterprise features setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up enterprise features: {e}")
    
    async def _setup_security_policies(self):
        """Setup security policies"""
        try:
            self.security_policies = {
                'message_content_filter': {
                    'enabled': True,
                    'blocked_patterns': ['spam', 'malware', 'suspicious'],
                    'action': 'block'
                },
                'user_access_control': {
                    'enabled': True,
                    'allowed_domains': [],
                    'blocked_users': [],
                    'action': 'restrict'
                },
                'chat_security': {
                    'enabled': True,
                    'require_admin_approval': False,
                    'encryption_required': False,
                    'action': 'monitor'
                }
            }
            
            logger.info("Security policies setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up security policies: {e}")
    
    async def _setup_compliance_rules(self):
        """Setup compliance rules"""
        try:
            self.compliance_rules = {
                'message_retention': {
                    'enabled': True,
                    'retention_period': 365,
                    'auto_delete': False
                },
                'content_moderation': {
                    'enabled': True,
                    'profanity_filter': True,
                    'hate_speech_filter': True,
                    'action': 'flag'
                },
                'audit_logging': {
                    'enabled': True,
                    'log_all_messages': True,
                    'log_user_actions': True,
                    'action': 'log'
                }
            }
            
            logger.info("Compliance rules setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up compliance rules: {e}")
    
    async def _setup_automation_triggers(self):
        """Setup automation triggers"""
        try:
            self.automation_triggers = {
                'message_received': {
                    'enabled': True,
                    'conditions': ['chat_type', 'user_role', 'message_content'],
                    'actions': ['send_notification', 'execute_workflow', 'ai_analysis']
                },
                'user_joined': {
                    'enabled': True,
                    'conditions': ['user_verification', 'chat_permissions'],
                    'actions': ['welcome_message', 'role_assignment', 'compliance_check']
                },
                'command_executed': {
                    'enabled': True,
                    'conditions': ['command_type', 'user_permissions'],
                    'actions': ['process_command', 'security_check', 'logging']
                }
            }
            
            logger.info("Automation triggers setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up automation triggers: {e}")
    
    async def _setup_automation(self):
        """Setup automation"""
        try:
            if not self.enterprise_automation:
                logger.warning("Automation service not available")
                return
            
            # Create WhatsApp-specific automation
            whatsapp_automation_data = {
                'name': 'WhatsApp Integration Automation',
                'description': 'Automation for WhatsApp integration events',
                'automation_type': 'integration',
                'priority': 'medium',
                'conditions': [
                    {
                        'type': 'event_triggered',
                        'platform': 'whatsapp',
                        'events': ['message_received', 'user_joined', 'command_executed']
                    }
                ],
                'actions': [
                    {
                        'type': 'notification',
                        'config': {
                            'channels': ['platform_admin'],
                            'message': 'WhatsApp integration event occurred',
                            'urgency': 'low'
                        }
                    }
                ],
                'schedule': None,
                'timeout': 300,
                'retry_policy': {
                    'max_retries': 2,
                    'backoff': 'exponential'
                },
                'notification_rules': [
                    {
                        'condition': 'on_error',
                        'channels': ['platform_admin'],
                        'urgency': 'medium'
                    }
                ],
                'metadata': {
                    'platform': 'whatsapp',
                    'integration_version': '1.0.0'
                }
            }
            
            result = await self.enterprise_automation.create_integration_automation('whatsapp', whatsapp_automation_data)
            if result.get('ok'):
                logger.info("WhatsApp automation created successfully")
            else:
                logger.error(f"Failed to create WhatsApp automation: {result.get('error')}")
            
        except Exception as e:
            logger.error(f"Error setting up automation: {e}")
    
    async def _setup_security_and_compliance(self):
        """Setup security and compliance monitoring"""
        try:
            # Setup monitoring for security events
            if self.whatsapp_config['enable_enterprise_features']:
                # Security monitoring
                await self._setup_security_monitoring()
                
                # Compliance monitoring
                await self._setup_compliance_monitoring()
            
            logger.info("Security and compliance setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up security and compliance: {e}")
    
    async def _setup_security_monitoring(self):
        """Setup security monitoring"""
        try:
            self.security_monitoring = {
                'message_anomaly_detection': {
                    'enabled': True,
                    'threshold': 0.8,
                    'action': 'alert'
                },
                'user_behavior_analysis': {
                    'enabled': True,
                    'baseline_period': 30,
                    'action': 'monitor'
                },
                'chat_security_monitoring': {
                    'enabled': True,
                    'security_score_threshold': 0.7,
                    'action': 'flag'
                }
            }
            
            logger.info("Security monitoring setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up security monitoring: {e}")
    
    async def _setup_compliance_monitoring(self):
        """Setup compliance monitoring"""
        try:
            self.compliance_monitoring = {
                'message_compliance_checking': {
                    'enabled': True,
                    'check_frequency': 'real_time',
                    'action': 'flag'
                },
                'user_activity_auditing': {
                    'enabled': True,
                    'audit_retention': 365,
                    'action': 'log'
                },
                'data_retention_management': {
                    'enabled': True,
                    'retention_policy': 'standard',
                    'action': 'manage'
                }
            }
            
            logger.info("Compliance monitoring setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up compliance monitoring: {e}")
    
    async def _setup_monitoring(self):
        """Setup monitoring"""
        try:
            self.performance_metrics = {
                'message_processing_time': 0.0,
                'command_response_time': 0.0,
                'ai_processing_time': 0.0,
                'security_check_time': 0.0,
                'compliance_check_time': 0.0,
                'automation_execution_time': 0.0,
                'webhook_response_time': 0.0
            }
            
            self._start_time = time.time()
            logger.info("Monitoring setup complete")
            
        except Exception as e:
            logger.error(f"Error setting up monitoring: {e}")
    
    async def _load_existing_data(self):
        """Load existing data"""
        try:
            # Mock implementation - would load from database
            logger.info("Existing data loaded")
            
        except Exception as e:
            logger.error(f"Error loading existing data: {e}")
    
    def _calculate_relevance_score(self, query: str, content: str) -> float:
        """Calculate relevance score for search"""
        try:
            query_words = query.lower().split()
            content_words = content.lower().split()
            
            matches = 0
            for word in query_words:
                if word in content_words:
                    matches += 1
            
            return matches / len(query_words) if query_words else 0.0
            
        except Exception as e:
            logger.error(f"Error calculating relevance score: {e}")
            return 0.0
    
    async def _perform_ai_search(self, query: str, workspace_id: str = None) -> List[Dict[str, Any]]:
        """Perform AI-enhanced search"""
        try:
            if not self.ai_service:
                return []
            
            # Create AI request
            ai_request = AIRequest(
                request_id=f"whatsapp_search_{int(time.time())}",
                task_type=AITaskType.SEARCH_QUERY,
                model_type=AIModelType.GPT_4,
                service_type=AIServiceType.OPENAI,
                input_data={
                    'query': query,
                    'context': 'whatsapp_search',
                    'workspace_id': workspace_id,
                    'message_history': [asdict(m) for chat_messages in self.message_history.values() for m in chat_messages]
                },
                context={
                    'platform': 'whatsapp',
                    'workspace_id': workspace_id
                },
                platform='whatsapp'
            )
            
            # Process AI request
            ai_response = await self.ai_service.process_ai_request(ai_request)
            
            if ai_response.ok and ai_response.output_data:
                return ai_response.output_data.get('results', [])
            
            return []
            
        except Exception as e:
            logger.error(f"Error performing AI search: {e}")
            return []
    
    async def _log_message_event(self, event_type: str, channel_id: str, data: Dict[str, Any]):
        """Log message event"""
        try:
            if self.enterprise_security:
                await self.enterprise_security.audit_event({
                    'event_type': event_type,
                    'user_id': data.get('user_id'),
                    'resource': 'whatsapp_message',
                    'action': event_type,
                    'result': 'success',
                    'ip_address': 'whatsapp',
                    'user_agent': 'whatsapp_bot',
                    'metadata': {
                        'channel_id': channel_id,
                        'platform': 'whatsapp',
                        'data': data
                    }
                })
                
        except Exception as e:
            logger.error(f"Error logging message event: {e}")
    
    async def close(self):
        """Close WhatsApp integration"""
        try:
            if self.http_session:
                await self.http_session.aclose()
            
            logger.info("WhatsApp Integration closed")
            
        except Exception as e:
            logger.error(f"Error closing WhatsApp integration: {e}")

# Global WhatsApp integration instance
atom_whatsapp_integration = AtomWhatsAppIntegration({
    'phone_number_id': os.getenv('WHATSAPP_PHONE_NUMBER_ID'),
    'business_account_id': os.getenv('WHATSAPP_BUSINESS_ACCOUNT_ID'),
    'access_token': os.getenv('WHATSAPP_ACCESS_TOKEN'),
    'webhook_url': os.getenv('WHATSAPP_WEBHOOK_URL'),
    'webhook_secret': os.getenv('WHATSAPP_WEBHOOK_SECRET'),
    'enable_enterprise_features': True,
    'security_level': 'standard',
    'compliance_standards': ['GDPR', 'SOC2', 'ISO27001'],
    'database': None,  # Would be actual database connection
    'cache': None,  # Would be actual cache client
    'security_service': atom_enterprise_security_service,
    'automation_service': atom_workflow_automation_service,
    'ai_service': ai_enhanced_service
})