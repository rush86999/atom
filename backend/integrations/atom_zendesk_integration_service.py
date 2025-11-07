"""
ATOM Zendesk Support Integration Service
Advanced customer support and ticketing system integration with Salesforce integration
"""

import os
import json
import logging
import asyncio
import time
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union, Callable, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import aiohttp
from collections import defaultdict, Counter
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
import hashlib
import hmac
import base64
from urllib.parse import urlencode

# Import existing ATOM services
try:
    from atom_enterprise_security_service import atom_enterprise_security_service, SecurityLevel, ComplianceStandard
    from atom_workflow_automation_service import atom_workflow_automation_service, AutomationPriority, AutomationStatus
    from ai_enhanced_service import ai_enhanced_service, AIRequest, AIResponse, AITaskType, AIModelType, AIServiceType
    from atom_ai_integration import atom_ai_integration
    from atom_slack_integration import atom_slack_integration
    from atom_teams_integration import atom_teams_integration
    from atom_google_chat_integration import atom_google_chat_integration
    from atom_discord_integration import atom_discord_integration
    from atom_telegram_integration import atom_telegram_integration
    from atom_whatsapp_integration import atom_whatsapp_integration
    from atom_zoom_integration import atom_zoom_integration
except ImportError as e:
    logging.warning(f"Enterprise services not available: {e}")

# Configure logging
logger = logging.getLogger(__name__)

class ZendeskTicketStatus(Enum):
    """Zendesk ticket status"""
    NEW = "new"
    OPEN = "open"
    PENDING = "pending"
    HOLD = "hold"
    SOLVED = "solved"
    CLOSED = "closed"

class ZendeskTicketPriority(Enum):
    """Zendesk ticket priority"""
    URGENT = "urgent"
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"

class ZendeskTicketType(Enum):
    """Zendesk ticket type"""
    QUESTION = "question"
    INCIDENT = "incident"
    PROBLEM = "problem"
    TASK = "task"

class SupportAnalyticsType(Enum):
    """Support analytics types"""
    RESPONSE_TIME = "response_time"
    RESOLUTION_TIME = "resolution_time"
    CUSTOMER_SATISFACTION = "customer_satisfaction"
    TICKET_VOLUME = "ticket_volume"
    AGENT_PERFORMANCE = "agent_performance"
    ESCALATION_RATE = "escalation_rate"
    FIRST_CONTACT_RESOLUTION = "first_contact_resolution"

@dataclass
class ZendeskTicket:
    """Zendesk ticket data model"""
    ticket_id: str
    subject: str
    description: str
    requester_id: str
    requester_email: str
    requester_name: str
    status: ZendeskTicketStatus
    priority: ZendeskTicketPriority
    ticket_type: ZendeskTicketType
    assignee_id: Optional[str]
    group_id: Optional[str]
    created_at: datetime
    updated_at: datetime
    due_at: Optional[datetime]
    tags: List[str]
    custom_fields: Dict[str, Any]
    comments: List[Dict[str, Any]]
    attachments: List[Dict[str, Any]]
    satisfaction_rating: Optional[str]
    platform: str
    metadata: Dict[str, Any]

@dataclass
class ZendeskUser:
    """Zendesk user data model"""
    user_id: str
    email: str
    name: str
    role: str
    phone: Optional[str]
    organization_id: Optional[str]
    tags: List[str]
    custom_fields: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

@dataclass
class ZendeskAgent:
    """Zendesk agent data model"""
    agent_id: str
    email: str
    name: str
    role: str
    group_ids: List[str]
    skills: List[str]
    availability: str
    status: str
    metrics: Dict[str, Any]
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]

@dataclass
class SupportAnalytics:
    """Support analytics data model"""
    analytics_id: str
    analytics_type: SupportAnalyticsType
    time_period: str
    start_date: datetime
    end_date: datetime
    metrics: Dict[str, Any]
    insights: List[str]
    recommendations: List[str]
    created_at: datetime
    metadata: Dict[str, Any]

class AtomZendeskIntegrationService:
    """Advanced Zendesk Support Integration Service"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = config.get('database')
        self.cache = config.get('cache')
        
        # Zendesk API configuration
        self.zendesk_config = {
            'subdomain': config.get('zendesk_subdomain'),
            'api_token': config.get('zendesk_api_token'),
            'username': config.get('zendesk_username'),
            'api_version': config.get('zendesk_api_version', 'v2'),
            'base_url': f"https://{config.get('zendesk_subdomain')}.zendesk.com/api/v2",
            'webhook_token': config.get('zendesk_webhook_token'),
            'oauth_token': config.get('zendesk_oauth_token'),
            'client_id': config.get('zendesk_client_id'),
            'client_secret': config.get('zendesk_client_secret'),
            'enable_salesforce_integration': config.get('enable_salesforce_integration', True),
            'salesforce_config': config.get('salesforce_config', {}),
            'ticket_auto_assignment': config.get('ticket_auto_assignment', True),
            'priority_auto_classification': config.get('priority_auto_classification', True),
            'sentiment_analysis': config.get('sentiment_analysis', True),
            'ai_response_suggestions': config.get('ai_response_suggestions', True),
            'sla_monitoring': config.get('sla_monitoring', True),
            'escalation_rules': config.get('escalation_rules', True),
            'customer_journey_tracking': config.get('customer_journey_tracking', True)
        }
        
        # API endpoints
        self.api_endpoints = {
            'tickets': '/tickets',
            'users': '/users',
            'organizations': '/organizations',
            'groups': '/groups',
            'views': '/views',
            'macros': '/macros',
            'automations': '/automations',
            'triggers': '/triggers',
            'ticket_fields': '/ticket_fields',
            'satisfaction_ratings': '/satisfaction_ratings',
            'search': '/search',
            'incremental': '/incremental'
        }
        
        # Integration state
        self.is_initialized = False
        self.webhook_handlers: Dict[str, Callable] = {}
        self.ticket_workflows: Dict[str, Dict[str, Any]] = {}
        self.escalation_rules: Dict[str, Dict[str, Any]] = {}
        self.agent_skills: Dict[str, List[str]] = {}
        self.customer_profiles: Dict[str, Dict[str, Any]] = {}
        
        # Salesforce integration
        self.salesforce_integration = None
        if self.zendesk_config['enable_salesforce_integration']:
            self.salesforce_integration = self._initialize_salesforce_integration()
        
        # Enterprise integration
        self.enterprise_security = config.get('security_service') or atom_enterprise_security_service
        self.enterprise_automation = config.get('automation_service') or atom_workflow_automation_service
        self.ai_service = config.get('ai_service') or ai_enhanced_service
        
        # Platform integrations
        self.platform_integrations = {
            'slack': atom_slack_integration,
            'teams': atom_teams_integration,
            'google_chat': atom_google_chat_integration,
            'discord': atom_discord_integration,
            'telegram': atom_telegram_integration,
            'whatsapp': atom_whatsapp_integration,
            'zoom': atom_zoom_integration
        }
        
        # Analytics and monitoring
        self.analytics_metrics = {
            'total_tickets': 0,
            'open_tickets': 0,
            'closed_tickets': 0,
            'tickets_created_today': 0,
            'tickets_resolved_today': 0,
            'average_response_time': 0.0,
            'average_resolution_time': 0.0,
            'customer_satisfaction_score': 0.0,
            'escalation_rate': 0.0,
            'first_contact_resolution_rate': 0.0,
            'agent_performance': defaultdict(dict),
            'ticket_volume_by_priority': defaultdict(int),
            'ticket_volume_by_type': defaultdict(int),
            'ticket_volume_by_channel': defaultdict(int),
            'response_time_by_channel': defaultdict(list),
            'resolution_time_by_priority': defaultdict(list)
        }
        
        # Performance metrics
        self.performance_metrics = {
            'api_response_time': 0.0,
            'webhook_processing_time': 0.0,
            'ai_analysis_time': 0.0,
            'salesforce_sync_time': 0.0,
            'ticket_creation_time': 0.0,
            'ticket_update_time': 0.0,
            'escalation_processing_time': 0.0,
            'analytics_generation_time': 0.0
        }
        
        # SLA configuration
        self.sla_config = {
            'urgent': {'first_response': 15, 'resolution': 120},  # minutes
            'high': {'first_response': 60, 'resolution': 480},
            'normal': {'first_response': 240, 'resolution': 1440},
            'low': {'first_response': 480, 'resolution': 2880}
        }
        
        logger.info("Zendesk Integration Service initialized")
    
    async def initialize(self) -> bool:
        """Initialize Zendesk Integration Service"""
        try:
            # Test Zendesk API connection
            await self._test_zendesk_connection()
            
            # Initialize Salesforce integration
            if self.salesforce_integration:
                await self._initialize_salesforce_connection()
            
            # Setup webhooks
            await self._setup_webhooks()
            
            # Setup ticket workflows
            await self._setup_ticket_workflows()
            
            # Setup escalation rules
            await self._setup_escalation_rules()
            
            # Setup enterprise features
            await self._setup_enterprise_features()
            
            # Setup security and compliance
            await self._setup_security_and_compliance()
            
            # Load existing tickets and user data
            await self._load_existing_data()
            
            # Start monitoring
            await self._start_monitoring()
            
            self.is_initialized = True
            logger.info("Zendesk Integration Service initialized successfully")
            return True
            
        except Exception as e:
            logger.error(f"Error initializing Zendesk Integration Service: {e}")
            return False
    
    async def create_ticket(self, ticket_data: Dict[str, Any], platform: str = None) -> Dict[str, Any]:
        """Create new ticket in Zendesk"""
        try:
            start_time = time.time()
            
            # Update analytics
            self.analytics_metrics['total_tickets'] += 1
            self.analytics_metrics['tickets_created_today'] += 1
            self.analytics_metrics['ticket_volume_by_priority'][ticket_data.get('priority', 'normal')] += 1
            self.analytics_metrics['ticket_volume_by_type'][ticket_data.get('type', 'question')] += 1
            if platform:
                self.analytics_metrics['ticket_volume_by_channel'][platform] += 1
            
            # Security and compliance check
            if self.zendesk_config['enable_enterprise_features']:
                security_check = await self._perform_security_check(ticket_data)
                if not security_check['passed']:
                    return {'success': False, 'error': security_check['reason']}
            
            # AI analysis for priority classification and sentiment
            if self.zendesk_config['priority_auto_classification'] or self.zendesk_config['sentiment_analysis']:
                ai_analysis = await self._analyze_ticket_with_ai(ticket_data)
                ticket_data.update(ai_analysis)
            
            # Prepare ticket payload
            ticket_payload = {
                'ticket': {
                    'subject': ticket_data.get('subject'),
                    'description': ticket_data.get('description'),
                    'requester': {
                        'name': ticket_data.get('requester_name'),
                        'email': ticket_data.get('requester_email')
                    },
                    'priority': ticket_data.get('priority', 'normal'),
                    'type': ticket_data.get('type', 'question'),
                    'status': 'new',
                    'tags': ticket_data.get('tags', []),
                    'custom_fields': ticket_data.get('custom_fields', {})
                }
            }
            
            # Add assignee if auto-assignment is enabled
            if self.zendesk_config['ticket_auto_assignment']:
                assignee_id = await self._auto_assign_ticket(ticket_data)
                if assignee_id:
                    ticket_payload['ticket']['assignee_id'] = assignee_id
            
            # Create ticket via API
            headers = self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{self.zendesk_config['base_url']}{self.api_endpoints['tickets']}",
                    headers=headers,
                    json=ticket_payload,
                    timeout=30.0
                )
                
                if response.status_code == 201:
                    ticket = response.json().get('ticket')
                    
                    # Update performance metrics
                    creation_time = time.time() - start_time
                    self.performance_metrics['ticket_creation_time'] = creation_time
                    
                    # Store ticket in local cache
                    await self._cache_ticket(ticket)
                    
                    # Sync with Salesforce if enabled
                    if self.salesforce_integration:
                        await self._sync_ticket_to_salesforce(ticket)
                    
                    # Notify relevant platforms
                    if platform and platform in self.platform_integrations:
                        await self._notify_platform_ticket_created(ticket, platform)
                    
                    # Trigger workflows
                    await self._trigger_ticket_workflows(ticket, 'created')
                    
                    logger.info(f"Ticket created successfully: {ticket['id']}")
                    return {
                        'success': True,
                        'ticket': ticket,
                        'ticket_id': ticket['id'],
                        'creation_time': creation_time
                    }
                else:
                    error_msg = f"Failed to create ticket: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Error creating ticket: {e}")
            return {'success': False, 'error': str(e)}
    
    async def update_ticket(self, ticket_id: str, update_data: Dict[str, Any], 
                         platform: str = None, comment: str = None) -> Dict[str, Any]:
        """Update existing ticket in Zendesk"""
        try:
            start_time = time.time()
            
            # Get current ticket data
            current_ticket = await self._get_ticket(ticket_id)
            if not current_ticket:
                return {'success': False, 'error': 'Ticket not found'}
            
            # Prepare update payload
            update_payload = {
                'ticket': {
                    'id': ticket_id,
                    'status': update_data.get('status'),
                    'priority': update_data.get('priority'),
                    'assignee_id': update_data.get('assignee_id'),
                    'tags': update_data.get('tags', current_ticket.get('tags', [])),
                    'custom_fields': update_data.get('custom_fields', {})
                }
            }
            
            # Add comment if provided
            if comment:
                update_payload['ticket']['comment'] = {
                    'body': comment,
                    'author_id': update_data.get('author_id'),
                    'public': update_data.get('public_comment', True)
                }
            
            # Update ticket via API
            headers = self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.put(
                    f"{self.zendesk_config['base_url']}{self.api_endpoints['tickets']}/{ticket_id}",
                    headers=headers,
                    json=update_payload,
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    updated_ticket = response.json().get('ticket')
                    
                    # Update performance metrics
                    update_time = time.time() - start_time
                    self.performance_metrics['ticket_update_time'] = update_time
                    
                    # Update local cache
                    await self._cache_ticket(updated_ticket)
                    
                    # Sync with Salesforce if enabled
                    if self.salesforce_integration:
                        await self._sync_ticket_to_salesforce(updated_ticket)
                    
                    # Notify relevant platforms
                    if platform and platform in self.platform_integrations:
                        await self._notify_platform_ticket_updated(updated_ticket, platform)
                    
                    # Check SLA compliance
                    if self.zendesk_config['sla_monitoring']:
                        await self._check_sla_compliance(updated_ticket)
                    
                    # Check for escalation
                    if self.zendesk_config['escalation_rules']:
                        await self._check_escalation(updated_ticket)
                    
                    # Trigger workflows
                    await self._trigger_ticket_workflows(updated_ticket, 'updated')
                    
                    logger.info(f"Ticket updated successfully: {ticket_id}")
                    return {
                        'success': True,
                        'ticket': updated_ticket,
                        'ticket_id': ticket_id,
                        'update_time': update_time
                    }
                else:
                    error_msg = f"Failed to update ticket: {response.status_code} - {response.text}"
                    logger.error(error_msg)
                    return {'success': False, 'error': error_msg}
                    
        except Exception as e:
            logger.error(f"Error updating ticket: {e}")
            return {'success': False, 'error': str(e)}
    
    async def get_tickets(self, filter_params: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get tickets from Zendesk with optional filtering"""
        try:
            start_time = time.time()
            
            # Build query parameters
            params = {}
            if filter_params:
                if 'status' in filter_params:
                    params['status'] = filter_params['status']
                if 'priority' in filter_params:
                    params['priority'] = filter_params['priority']
                if 'assignee_id' in filter_params:
                    params['assignee_id'] = filter_params['assignee_id']
                if 'created_since' in filter_params:
                    params['created_since'] = filter_params['created_since']
                if 'limit' in filter_params:
                    params['per_page'] = min(filter_params['limit'], 100)
            
            # Fetch tickets via API
            headers = self._get_auth_headers()
            all_tickets = []
            
            async with httpx.AsyncClient() as client:
                url = f"{self.zendesk_config['base_url']}{self.api_endpoints['tickets']}"
                
                while url:
                    response = await client.get(url, headers=headers, params=params, timeout=30.0)
                    
                    if response.status_code == 200:
                        data = response.json()
                        tickets = data.get('tickets', [])
                        all_tickets.extend(tickets)
                        
                        # Check for pagination
                        if 'next_page' in data and data['next_page']:
                            url = data['next_page']
                        else:
                            url = None
                    else:
                        error_msg = f"Failed to fetch tickets: {response.status_code} - {response.text}"
                        logger.error(error_msg)
                        return []
            
            # Update performance metrics
            fetch_time = time.time() - start_time
            self.performance_metrics['api_response_time'] = fetch_time
            
            # Update analytics
            self.analytics_metrics['open_tickets'] = len([t for t in all_tickets if t['status'] in ['new', 'open', 'pending', 'hold']])
            self.analytics_metrics['closed_tickets'] = len([t for t in all_tickets if t['status'] in ['solved', 'closed']])
            
            return all_tickets
            
        except Exception as e:
            logger.error(f"Error fetching tickets: {e}")
            return []
    
    async def generate_support_analytics(self, analytics_type: SupportAnalyticsType, 
                                     time_period: str = '7d') -> Dict[str, Any]:
        """Generate support analytics"""
        try:
            start_time = time.time()
            
            # Calculate date range
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=7)  # Default to 7 days
            
            # Fetch tickets within date range
            filter_params = {
                'created_since': start_date.isoformat(),
                'limit': 1000
            }
            tickets = await self.get_tickets(filter_params)
            
            # Generate analytics based on type
            if analytics_type == SupportAnalyticsType.RESPONSE_TIME:
                analytics_data = await self._generate_response_time_analytics(tickets)
            elif analytics_type == SupportAnalyticsType.RESOLUTION_TIME:
                analytics_data = await self._generate_resolution_time_analytics(tickets)
            elif analytics_type == SupportAnalyticsType.CUSTOMER_SATISFACTION:
                analytics_data = await self._generate_satisfaction_analytics(tickets)
            elif analytics_type == SupportAnalyticsType.TICKET_VOLUME:
                analytics_data = await self._generate_volume_analytics(tickets)
            elif analytics_type == SupportAnalyticsType.AGENT_PERFORMANCE:
                analytics_data = await self._generate_agent_performance_analytics(tickets)
            elif analytics_type == SupportAnalyticsType.ESCALATION_RATE:
                analytics_data = await self._generate_escalation_analytics(tickets)
            elif analytics_type == SupportAnalyticsType.FIRST_CONTACT_RESOLUTION:
                analytics_data = await self._generate_fcr_analytics(tickets)
            else:
                analytics_data = {'error': 'Unsupported analytics type'}
            
            # Add AI-powered insights
            if self.zendesk_config['ai_response_suggestions']:
                insights = await self._generate_ai_insights(analytics_data, tickets)
                analytics_data['ai_insights'] = insights
            
            # Create analytics object
            analytics = SupportAnalytics(
                analytics_id=f"analytics_{int(time.time())}",
                analytics_type=analytics_type,
                time_period=time_period,
                start_date=start_date,
                end_date=end_date,
                metrics=analytics_data,
                insights=analytics_data.get('insights', []),
                recommendations=analytics_data.get('recommendations', []),
                created_at=datetime.utcnow(),
                metadata={'generated_by': 'atom_zendesk_integration'}
            )
            
            # Update performance metrics
            generation_time = time.time() - start_time
            self.performance_metrics['analytics_generation_time'] = generation_time
            
            return {
                'success': True,
                'analytics': asdict(analytics),
                'generation_time': generation_time
            }
            
        except Exception as e:
            logger.error(f"Error generating support analytics: {e}")
            return {'success': False, 'error': str(e)}
    
    async def _analyze_ticket_with_ai(self, ticket_data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze ticket with AI for priority classification and sentiment"""
        try:
            start_time = time.time()
            
            # Prepare AI request for analysis
            ai_request = AIRequest(
                request_id=f"ticket_analysis_{int(time.time())}",
                task_type=AITaskType.CONTENT_ANALYSIS,
                model_type=AIModelType.GPT_4,
                service_type=AIServiceType.OPENAI,
                input_data={
                    'text': f"Subject: {ticket_data.get('subject', '')}\n\nDescription: {ticket_data.get('description', '')}",
                    'context': 'support_ticket_analysis',
                    'analysis_type': 'priority_and_sentiment'
                },
                context={
                    'platform': 'zendesk',
                    'task': 'ticket_analysis'
                },
                platform='zendesk'
            )
            
            ai_response = await self.ai_service.process_ai_request(ai_request)
            
            if ai_response.ok and ai_response.output_data:
                analysis_result = ai_response.output_data
                
                ai_suggestions = {
                    'suggested_priority': analysis_result.get('suggested_priority', 'normal'),
                    'sentiment': analysis_result.get('sentiment', 'neutral'),
                    'urgency_score': analysis_result.get('urgency_score', 0.5),
                    'complexity_score': analysis_result.get('complexity_score', 0.5),
                    'suggested_agent_skills': analysis_result.get('suggested_agent_skills', []),
                    'response_suggestion': analysis_result.get('response_suggestion', ''),
                    'estimated_resolution_time': analysis_result.get('estimated_resolution_time', 60)
                }
            else:
                ai_suggestions = {
                    'suggested_priority': ticket_data.get('priority', 'normal'),
                    'sentiment': 'neutral',
                    'urgency_score': 0.5,
                    'complexity_score': 0.5,
                    'suggested_agent_skills': [],
                    'response_suggestion': '',
                    'estimated_resolution_time': 60
                }
            
            # Update performance metrics
            analysis_time = time.time() - start_time
            self.performance_metrics['ai_analysis_time'] = analysis_time
            
            return ai_suggestions
            
        except Exception as e:
            logger.error(f"Error analyzing ticket with AI: {e}")
            return {
                'suggested_priority': ticket_data.get('priority', 'normal'),
                'sentiment': 'neutral',
                'urgency_score': 0.5,
                'complexity_score': 0.5,
                'suggested_agent_skills': [],
                'response_suggestion': '',
                'estimated_resolution_time': 60
            }
    
    async def _auto_assign_ticket(self, ticket_data: Dict[str, Any]) -> Optional[str]:
        """Auto-assign ticket to appropriate agent"""
        try:
            # Get suggested skills from AI analysis
            suggested_skills = ticket_data.get('suggested_agent_skills', [])
            
            # Find available agents with matching skills
            available_agents = await self._get_available_agents()
            
            for agent in available_agents:
                agent_skills = self.agent_skills.get(agent['id'], [])
                if any(skill in agent_skills for skill in suggested_skills):
                    # Check agent workload
                    agent_workload = await self._get_agent_workload(agent['id'])
                    if agent_workload < 5:  # Max 5 tickets per agent
                        return agent['id']
            
            # If no specific match, assign to agent with lowest workload
            if available_agents:
                min_workload_agent = min(available_agents, 
                                       key=lambda a: self.analytics_metrics['agent_performance'].get(a['id'], {}).get('open_tickets', 0))
                return min_workload_agent['id']
            
            return None
            
        except Exception as e:
            logger.error(f"Error auto-assigning ticket: {e}")
            return None
    
    async def _initialize_salesforce_integration(self):
        """Initialize Salesforce integration"""
        try:
            from atom_salesforce_integration import atom_salesforce_integration
            self.salesforce_integration = atom_salesforce_integration
            logger.info("Salesforce integration initialized")
            
        except ImportError:
            logger.warning("Salesforce integration not available")
            self.salesforce_integration = None
    
    async def _test_zendesk_connection(self):
        """Test Zendesk API connection"""
        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.zendesk_config['base_url']}/tickets/count",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    logger.info("Zendesk API connection test successful")
                    return True
                else:
                    raise Exception(f"Zendesk API test failed: {response.status_code}")
                    
        except Exception as e:
            logger.error(f"Zendesk connection test failed: {e}")
            raise
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers for Zendesk API"""
        if self.zendesk_config['oauth_token']:
            return {
                'Authorization': f"Bearer {self.zendesk_config['oauth_token']}",
                'Content-Type': 'application/json'
            }
        elif self.zendesk_config['api_token']:
            credentials = f"{self.zendesk_config['username']}/token:{self.zendesk_config['api_token']}"
            encoded_credentials = base64.b64encode(credentials.encode()).decode()
            return {
                'Authorization': f"Basic {encoded_credentials}",
                'Content-Type': 'application/json'
            }
        else:
            raise Exception("No authentication method configured")
    
    async def _cache_ticket(self, ticket: Dict[str, Any]):
        """Cache ticket data locally"""
        try:
            if self.cache:
                cache_key = f"zendesk_ticket:{ticket['id']}"
                await self.cache.set(cache_key, ticket, ttl=3600)  # 1 hour
        except Exception as e:
            logger.error(f"Error caching ticket: {e}")
    
    async def _get_ticket(self, ticket_id: str) -> Optional[Dict[str, Any]]:
        """Get ticket from Zendesk API or cache"""
        try:
            # Try cache first
            if self.cache:
                cache_key = f"zendesk_ticket:{ticket_id}"
                cached_ticket = await self.cache.get(cache_key)
                if cached_ticket:
                    return cached_ticket
            
            # Fetch from API
            headers = self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.zendesk_config['base_url']}{self.api_endpoints['tickets']}/{ticket_id}",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    ticket = response.json().get('ticket')
                    await self._cache_ticket(ticket)
                    return ticket
                else:
                    return None
                    
        except Exception as e:
            logger.error(f"Error fetching ticket: {e}")
            return None
    
    async def _get_available_agents(self) -> List[Dict[str, Any]]:
        """Get list of available agents"""
        try:
            headers = self._get_auth_headers()
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{self.zendesk_config['base_url']}{self.api_endpoints['users']}?role=agent",
                    headers=headers,
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    users = response.json().get('users', [])
                    return [user for user in users if user.get('role') == 'agent']
                else:
                    return []
                    
        except Exception as e:
            logger.error(f"Error fetching available agents: {e}")
            return []
    
    async def _get_agent_workload(self, agent_id: str) -> int:
        """Get agent's current workload"""
        try:
            filter_params = {
                'assignee_id': agent_id,
                'status': 'new,open,pending,hold'
            }
            tickets = await self.get_tickets(filter_params)
            return len(tickets)
            
        except Exception as e:
            logger.error(f"Error getting agent workload: {e}")
            return 0
    
    async def get_service_status(self) -> Dict[str, Any]:
        """Get Zendesk Integration service status"""
        try:
            return {
                'service': 'zendesk_integration',
                'status': 'active' if self.is_initialized else 'inactive',
                'zendesk_config': {
                    'subdomain': self.zendesk_config['subdomain'],
                    'api_version': self.zendesk_config['api_version'],
                    'auto_assignment': self.zendesk_config['ticket_auto_assignment'],
                    'ai_features': {
                        'priority_classification': self.zendesk_config['priority_auto_classification'],
                        'sentiment_analysis': self.zendesk_config['sentiment_analysis'],
                        'response_suggestions': self.zendesk_config['ai_response_suggestions']
                    },
                    'salesforce_integration': self.zendesk_config['enable_salesforce_integration'],
                    'sla_monitoring': self.zendesk_config['sla_monitoring']
                },
                'analytics_metrics': self.analytics_metrics,
                'performance_metrics': self.performance_metrics,
                'uptime': time.time() - (self._start_time if hasattr(self, '_start_time') else time.time())
            }
        except Exception as e:
            logger.error(f"Error getting service status: {e}")
            return {'error': str(e), 'service': 'zendesk_integration'}
    
    async def close(self):
        """Close Zendesk Integration Service"""
        try:
            logger.info("Zendesk Integration Service closed")
            
        except Exception as e:
            logger.error(f"Error closing Zendesk Integration Service: {e}")

# Global Zendesk Integration service instance
atom_zendesk_integration_service = AtomZendeskIntegrationService({
    'zendesk_subdomain': os.getenv('ZENDESK_SUBDOMAIN', 'your-subdomain'),
    'zendesk_api_token': os.getenv('ZENDESK_API_TOKEN', 'your-api-token'),
    'zendesk_username': os.getenv('ZENDESK_USERNAME', 'your-username'),
    'zendesk_webhook_token': os.getenv('ZENDESK_WEBHOOK_TOKEN', 'your-webhook-token'),
    'enable_salesforce_integration': True,
    'salesforce_config': {
        'client_id': os.getenv('SALESFORCE_CLIENT_ID'),
        'client_secret': os.getenv('SALESFORCE_CLIENT_SECRET'),
        'username': os.getenv('SALESFORCE_USERNAME'),
        'password': os.getenv('SALESFORCE_PASSWORD'),
        'security_token': os.getenv('SALESFORCE_SECURITY_TOKEN')
    },
    'ticket_auto_assignment': True,
    'priority_auto_classification': True,
    'sentiment_analysis': True,
    'ai_response_suggestions': True,
    'sla_monitoring': True,
    'escalation_rules': True,
    'customer_journey_tracking': True,
    'database': None,  # Would be actual database connection
    'cache': None,  # Would be actual cache client
    'security_service': atom_enterprise_security_service,
    'automation_service': atom_workflow_automation_service,
    'ai_service': ai_enhanced_service
})