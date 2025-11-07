"""
ATOM Cross-Service AI Intelligence Service
Unified AI system connecting all integrations with intelligent workflows
Following ATOM service patterns and conventions
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
from typing import Dict, List, Optional, Any, Tuple, Union
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from loguru import logger

# AI/ML Libraries
try:
    import networkx as nx  # Graph analysis for relationships
except ImportError:
    nx = None

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    SentenceTransformer = None

try:
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.cluster import KMeans
    from sklearn.metrics.pairwise import cosine_similarity
except ImportError:
    TfidfVectorizer = KMeans = cosine_similarity = None

# Integration Services
try:
    from google_drive_service import create_google_drive_service
except ImportError:
    create_google_drive_service = None

try:
    from zendesk_service import create_zendesk_service
except ImportError:
    create_zendesk_service = None

try:
    from quickbooks_service import create_quickbooks_service
except ImportError:
    create_quickbooks_service = None

try:
    from hubspot_service import create_hubspot_service
except ImportError:
    create_hubspot_service = None

try:
    from document_intelligence_service import create_document_intelligence_service
except ImportError:
    create_document_intelligence_service = None

class IntegrationType(Enum):
    """Supported integration types"""
    GOOGLE_DRIVE = "google_drive"
    ZENDESK = "zendesk"
    QUICKBOOKS = "quickbooks"
    HUBSPOT = "hubspot"

class ActionType(Enum):
    """AI action types"""
    DATA_SYNTHESIS = "data_synthesis"
    WORKFLOW_TRIGGER = "workflow_trigger"
    INSIGHT_GENERATION = "insight_generation"
    PREDICTION = "prediction"
    OPTIMIZATION = "optimization"

@dataclass
class ServiceData:
    """Unified data structure from any service"""
    service_type: IntegrationType
    service_id: str
    item_id: str
    title: str
    content: str
    metadata: Dict[str, Any]
    timestamp: datetime
    tags: List[str]
    importance_score: float
    relationships: List[Dict[str, Any]] = None
    
    def __post_init__(self):
        if self.relationships is None:
            self.relationships = []

@dataclass
class CrossServiceInsight:
    """Cross-service AI-generated insights"""
    insight_id: str
    insight_type: str
    title: str
    description: str
    confidence_score: float
    business_impact: str
    action_items: List[Dict[str, Any]]
    related_data: List[ServiceData]
    generated_at: datetime
    services_involved: List[IntegrationType]
    
    def __post_init__(self):
        if self.action_items is None:
            self.action_items = []

@dataclass
class WorkflowRecommendation:
    """AI-generated workflow recommendations"""
    workflow_id: str
    workflow_name: str
    description: str
    trigger_condition: str
    services: List[IntegrationType]
    steps: List[Dict[str, Any]]
    expected_benefit: str
    confidence_score: float
    priority: str
    
    def __post_init__(self):
        if self.steps is None:
            self.steps = []

@dataclass
class BusinessPrediction:
    """AI-powered business predictions"""
    prediction_id: str
    prediction_type: str
    title: str
    prediction: str
    confidence_interval: Tuple[float, float]
    influencing_factors: List[Dict[str, Any]]
    business_impact: str
    timeline: str
    generated_at: datetime
    services_involved: List[IntegrationType]

class CrossServiceAIService:
    """Unified AI intelligence service for cross-service workflows and insights"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        # Service instances
        self.services = {}
        self._initialize_services()
        
        # AI models and tools
        self.sentence_model = None
        self.tfidf_vectorizer = None
        self.knowledge_graph = None
        
        # Initialize AI models
        self._initialize_ai_models()
        
        # Data storage (in production, this would be a database)
        self.service_data = []  # List[ServiceData]
        self.insights = []  # List[CrossServiceInsight]
        self.workflows = []  # List[WorkflowRecommendation]
        
        logger.info(f"Cross-Service AI Service initialized with {len(self.services)} integrations")
    
    def _initialize_services(self):
        """Initialize all integration services"""
        try:
            if create_google_drive_service:
                self.services[IntegrationType.GOOGLE_DRIVE] = create_google_drive_service()
                logger.info("Google Drive service initialized for Cross-Service AI")
        except Exception as e:
            logger.warning(f"Failed to initialize Google Drive service: {e}")
        
        try:
            if create_zendesk_service:
                self.services[IntegrationType.ZENDESK] = create_zendesk_service()
                logger.info("Zendesk service initialized for Cross-Service AI")
        except Exception as e:
            logger.warning(f"Failed to initialize Zendesk service: {e}")
        
        try:
            if create_quickbooks_service:
                self.services[IntegrationType.QUICKBOOKS] = create_quickbooks_service()
                logger.info("QuickBooks service initialized for Cross-Service AI")
        except Exception as e:
            logger.warning(f"Failed to initialize QuickBooks service: {e}")
        
        try:
            if create_hubspot_service:
                self.services[IntegrationType.HUBSPOT] = create_hubspot_service()
                logger.info("HubSpot service initialized for Cross-Service AI")
        except Exception as e:
            logger.warning(f"Failed to initialize HubSpot service: {e}")
        
        try:
            if create_document_intelligence_service:
                self.services['document_intelligence'] = create_document_intelligence_service()
                logger.info("Document Intelligence service initialized for Cross-Service AI")
        except Exception as e:
            logger.warning(f"Failed to initialize Document Intelligence service: {e}")
    
    def _initialize_ai_models(self):
        """Initialize AI models and tools"""
        try:
            # Initialize sentence transformer for embeddings
            if SentenceTransformer:
                self.sentence_model = SentenceTransformer('all-MiniLM-L6-v2')
                logger.info("Sentence transformer model loaded for Cross-Service AI")
            
            # Initialize text vectorizer
            if TfidfVectorizer:
                self.tfidf_vectorizer = TfidfVectorizer(
                    max_features=10000,
                    stop_words='english',
                    ngram_range=(1, 3)
                )
                logger.info("TF-IDF vectorizer initialized for Cross-Service AI")
            
            # Initialize knowledge graph
            if nx:
                self.knowledge_graph = nx.Graph()
                logger.info("Knowledge graph initialized for Cross-Service AI")
                
        except Exception as e:
            logger.error(f"Failed to initialize AI models: {e}")
    
    async def collect_service_data(self, service_type: IntegrationType, access_token: str, limit: int = 20) -> List[ServiceData]:
        """Collect data from a specific service"""
        try:
            service = self.services.get(service_type)
            if not service:
                logger.warning(f"Service {service_type} not available")
                return []
            
            data = []
            
            if service_type == IntegrationType.GOOGLE_DRIVE:
                data = await self._collect_google_drive_data(service, access_token, limit)
            elif service_type == IntegrationType.ZENDESK:
                data = await self._collect_zendesk_data(service, access_token, limit)
            elif service_type == IntegrationType.QUICKBOOKS:
                data = await self._collect_quickbooks_data(service, access_token, limit)
            elif service_type == IntegrationType.HUBSPOT:
                data = await self._collect_hubspot_data(service, access_token, limit)
            
            logger.info(f"Collected {len(data)} items from {service_type}")
            return data
            
        except Exception as e:
            logger.error(f"Failed to collect data from {service_type}: {e}")
            return []
    
    async def _collect_google_drive_data(self, service, access_token: str, limit: int) -> List[ServiceData]:
        """Collect data from Google Drive"""
        data = []
        
        try:
            # Get files from Google Drive
            files_response = await service.list_files(access_token, limit=limit)
            files = files_response.get('files', [])
            
            document_service = self.services.get('document_intelligence')
            
            for file_item in files[:limit]:
                # Analyze document if available
                importance_score = 0.5  # Default
                tags = []
                content = ""
                
                if document_service:
                    try:
                        analysis = await document_service.analyze_document(file_item['id'], access_token)
                        importance_score = analysis.importance_score or 0.5
                        tags = analysis.categories + analysis.keywords
                        content = analysis.text_content or ""
                    except:
                        pass
                
                service_data = ServiceData(
                    service_type=IntegrationType.GOOGLE_DRIVE,
                    service_id=file_item['id'],
                    item_id=file_item['id'],
                    title=file_item.get('name', ''),
                    content=content,
                    metadata={
                        'file_type': file_item.get('mimeType', ''),
                        'size': file_item.get('size', 0),
                        'created_time': file_item.get('createdTime', ''),
                        'modified_time': file_item.get('modifiedTime', '')
                    },
                    timestamp=datetime.fromisoformat(file_item.get('modifiedTime', '').replace('Z', '+00:00')),
                    tags=tags,
                    importance_score=importance_score
                )
                
                data.append(service_data)
            
        except Exception as e:
            logger.error(f"Error collecting Google Drive data: {e}")
        
        return data
    
    async def _collect_zendesk_data(self, service, access_token: str, limit: int) -> List[ServiceData]:
        """Collect data from Zendesk"""
        data = []
        
        try:
            # Get tickets from Zendesk
            tickets_response = await service.get_tickets(access_token, limit=limit)
            tickets = tickets_response.get('tickets', [])
            
            for ticket in tickets[:limit]:
                importance_score = 0.5
                
                # Calculate importance based on ticket properties
                if ticket.get('priority') == 'urgent':
                    importance_score = 0.9
                elif ticket.get('priority') == 'high':
                    importance_score = 0.7
                
                tags = [ticket.get('status', ''), ticket.get('priority', '')]
                if ticket.get('tags'):
                    tags.extend(ticket['tags'])
                
                service_data = ServiceData(
                    service_type=IntegrationType.ZENDESK,
                    service_id=str(ticket.get('id', '')),
                    item_id=str(ticket.get('id', '')),
                    title=ticket.get('subject', ''),
                    content=f"{ticket.get('description', '')} {' '.join(ticket.get('tags', []))}",
                    metadata={
                        'status': ticket.get('status', ''),
                        'priority': ticket.get('priority', ''),
                        'created_at': ticket.get('created_at', ''),
                        'updated_at': ticket.get('updated_at', ''),
                        'requester': ticket.get('requester', {}),
                        'assignee': ticket.get('assignee', {})
                    },
                    timestamp=datetime.fromisoformat(ticket.get('updated_at', '').replace('Z', '+00:00')),
                    tags=tags,
                    importance_score=importance_score
                )
                
                data.append(service_data)
            
        except Exception as e:
            logger.error(f"Error collecting Zendesk data: {e}")
        
        return data
    
    async def _collect_quickbooks_data(self, service, access_token: str, limit: int) -> List[ServiceData]:
        """Collect data from QuickBooks"""
        data = []
        
        try:
            # Get invoices from QuickBooks
            invoices_response = await service.get_invoices(access_token, limit=limit)
            invoices = invoices_response.get('invoices', [])
            
            for invoice in invoices[:limit]:
                importance_score = 0.5
                
                # Calculate importance based on amount
                total = invoice.get('total', 0)
                if total > 10000:
                    importance_score = 0.9
                elif total > 5000:
                    importance_score = 0.7
                elif total > 1000:
                    importance_score = 0.6
                
                tags = ['invoice', f"amount_{total}", invoice.get('status', '')]
                
                service_data = ServiceData(
                    service_type=IntegrationType.QUICKBOOKS,
                    service_id=str(invoice.get('Id', '')),
                    item_id=str(invoice.get('Id', '')),
                    title=f"Invoice {invoice.get('DocNumber', '')}",
                    content=f"Invoice for {total} to {invoice.get('CustomerRef', {}).get('name', '')}",
                    metadata={
                        'doc_number': invoice.get('DocNumber', ''),
                        'total': total,
                        'status': invoice.get('status', ''),
                        'customer': invoice.get('CustomerRef', {}),
                        'due_date': invoice.get('DueDate', ''),
                        'created_date': invoice.get('MetaData', {}).get('CreateTime', '')
                    },
                    timestamp=datetime.fromisoformat(invoice.get('MetaData', {}).get('LastUpdatedTime', '').replace('Z', '+00:00')),
                    tags=tags,
                    importance_score=importance_score
                )
                
                data.append(service_data)
            
        except Exception as e:
            logger.error(f"Error collecting QuickBooks data: {e}")
        
        return data
    
    async def _collect_hubspot_data(self, service, access_token: str, limit: int) -> List[ServiceData]:
        """Collect data from HubSpot"""
        data = []
        
        try:
            # Get contacts from HubSpot
            contacts_response = await service.get_contacts(access_token, limit=limit)
            contacts = contacts_response.get('results', [])
            
            for contact in contacts[:limit]:
                properties = contact.get('properties', {})
                
                importance_score = 0.5
                
                # Calculate importance based on lifecycle stage
                lifecycle_stage = properties.get('lifecyclestage', {}).get('value', '')
                if lifecycle_stage in ['opportunity', 'evangelist']:
                    importance_score = 0.9
                elif lifecycle_stage in ['lead', 'marketingqualifiedlead']:
                    importance_score = 0.7
                
                tags = [lifecycle_stage, 'contact']
                if properties.get('company'):
                    tags.append(properties['company']['value'])
                
                service_data = ServiceData(
                    service_type=IntegrationType.HUBSPOT,
                    service_id=str(contact.get('id', '')),
                    item_id=str(contact.get('id', '')),
                    title=f"Contact: {properties.get('firstname', {}).get('value', '')} {properties.get('lastname', {}).get('value', '')}",
                    content=f"{properties.get('firstname', {}).get('value', '')} {properties.get('lastname', {}).get('value', '')} {properties.get('company', {}).get('value', '')} {properties.get('email', {}).get('value', '')}",
                    metadata={
                        'first_name': properties.get('firstname', {}).get('value', ''),
                        'last_name': properties.get('lastname', {}).get('value', ''),
                        'email': properties.get('email', {}).get('value', ''),
                        'company': properties.get('company', {}).get('value', ''),
                        'lifecycle_stage': lifecycle_stage,
                        'created_at': contact.get('createdAt', ''),
                        'updated_at': contact.get('updatedAt', '')
                    },
                    timestamp=datetime.fromisoformat(contact.get('updatedAt', '').replace('Z', '+00:00')),
                    tags=tags,
                    importance_score=importance_score
                )
                
                data.append(service_data)
            
        except Exception as e:
            logger.error(f"Error collecting HubSpot data: {e}")
        
        return data
    
    async def collect_all_service_data(self, access_tokens: Dict[IntegrationType, str], limit: int = 10) -> List[ServiceData]:
        """Collect data from all available services"""
        all_data = []
        
        # Create tasks for concurrent data collection
        tasks = []
        for service_type, access_token in access_tokens.items():
            if service_type in self.services:
                task = self.collect_service_data(service_type, access_token, limit)
                tasks.append(task)
        
        # Execute concurrently
        if tasks:
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in results:
                if isinstance(result, list):
                    all_data.extend(result)
                else:
                    logger.error(f"Error in data collection: {result}")
        
        # Store data for analysis
        self.service_data = all_data
        
        logger.info(f"Collected total {len(all_data)} items from all services")
        return all_data
    
    async def generate_cross_service_insights(self, service_data: Optional[List[ServiceData]] = None) -> List[CrossServiceInsight]:
        """Generate AI-powered cross-service insights"""
        try:
            if service_data is None:
                service_data = self.service_data
            
            if not service_data:
                logger.warning("No service data available for insights")
                return []
            
            insights = []
            
            # Generate different types of insights
            insights.extend(await self._generate_trend_insights(service_data))
            insights.extend(await self._generate_correlation_insights(service_data))
            insights.extend(await self._generate_efficiency_insights(service_data))
            insights.extend(await self._generate_opportunity_insights(service_data))
            
            # Store insights
            self.insights = insights
            
            logger.info(f"Generated {len(insights)} cross-service insights")
            return insights
            
        except Exception as e:
            logger.error(f"Failed to generate cross-service insights: {e}")
            return []
    
    async def _generate_trend_insights(self, service_data: List[ServiceData]) -> List[CrossServiceInsight]:
        """Generate trend-based insights"""
        insights = []
        
        try:
            # Analyze data trends across services
            service_data_by_type = {}
            for data in service_data:
                service_type = data.service_type
                if service_type not in service_data_by_type:
                    service_data_by_type[service_type] = []
                service_data_by_type[service_type].append(data)
            
            # Generate trend insights
            for service_type, data_list in service_data_by_type.items():
                if len(data_list) < 3:  # Need minimum data for trends
                    continue
                
                # Calculate trends
                recent_data = sorted(data_list, key=lambda x: x.timestamp, reverse=True)[:7]
                older_data = sorted(data_list, key=lambda x: x.timestamp, reverse=True)[7:14]
                
                # Example: Increasing support tickets trend
                if service_type == IntegrationType.ZENDESK:
                    recent_high_priority = len([d for d in recent_data if 'urgent' in d.tags or 'high' in d.tags])
                    older_high_priority = len([d for d in older_data if 'urgent' in d.tags or 'high' in d.tags])
                    
                    if recent_high_priority > older_high_priority * 1.5:
                        insight = CrossServiceInsight(
                            insight_id=str(uuid.uuid4()),
                            insight_type="trend",
                            title="Increasing High-Priority Support Issues",
                            description=f"High-priority support tickets have increased by {((recent_high_priority/older_high_priority - 1) * 100):.1f}% in the recent period",
                            confidence_score=0.8,
                            business_impact="Potential customer satisfaction issues and increased support workload",
                            action_items=[
                                {"action": "Investigate root cause of increasing issues", "priority": "high"},
                                {"action": "Review support staffing levels", "priority": "medium"},
                                {"action": "Analyze issue patterns for proactive measures", "priority": "medium"}
                            ],
                            related_data=recent_data[:5],
                            generated_at=datetime.utcnow(),
                            services_involved=[IntegrationType.ZENDESK]
                        )
                        insights.append(insight)
                
                # Example: Financial document trend
                elif service_type == IntegrationType.GOOGLE_DRIVE:
                    financial_docs = [d for d in recent_data if any('financial' in tag.lower() or 'invoice' in tag.lower() for tag in d.tags)]
                    if len(financial_docs) > 3:
                        insight = CrossServiceInsight(
                            insight_id=str(uuid.uuid4()),
                            insight_type="trend",
                            title="Increased Financial Document Activity",
                            description=f"Financial documents and invoices are being created/updated at a higher rate recently",
                            confidence_score=0.7,
                            business_impact="Potential increased financial activity that may require attention",
                            action_items=[
                                {"action": "Review financial document workflows", "priority": "medium"},
                                {"action": "Ensure proper financial oversight", "priority": "medium"}
                            ],
                            related_data=financial_docs[:5],
                            generated_at=datetime.utcnow(),
                            services_involved=[IntegrationType.GOOGLE_DRIVE]
                        )
                        insights.append(insight)
            
        except Exception as e:
            logger.error(f"Error generating trend insights: {e}")
        
        return insights
    
    async def _generate_correlation_insights(self, service_data: List[ServiceData]) -> List[CrossServiceInsight]:
        """Generate correlation-based insights"""
        insights = []
        
        try:
            # Find correlations between services
            google_drive_data = [d for d in service_data if d.service_type == IntegrationType.GOOGLE_DRIVE]
            zendesk_data = [d for d in service_data if d.service_type == IntegrationType.ZENDESK]
            quickbooks_data = [d for d in service_data if d.service_type == IntegrationType.QUICKBOOKS]
            
            # Correlate documents and support tickets
            if google_drive_data and zendesk_data:
                # Look for related content
                for doc in google_drive_data[:5]:
                    for ticket in zendesk_data[:5]:
                        # Simple correlation check (in production, would use semantic similarity)
                        doc_words = set(doc.title.lower().split() + doc.tags)
                        ticket_words = set(ticket.title.lower().split() + ticket.tags)
                        
                        if doc_words & ticket_words:  # Overlapping words
                            insight = CrossServiceInsight(
                                insight_id=str(uuid.uuid4()),
                                insight_type="correlation",
                                title="Related Document and Support Ticket Found",
                                description=f"Document '{doc.title}' appears to be related to support ticket '{ticket.title}'",
                                confidence_score=0.6,
                                business_impact="Potential issue documentation needs improvement",
                                action_items=[
                                    {"action": "Link support ticket to relevant documentation", "priority": "medium"},
                                    {"action": "Review document completeness for issue resolution", "priority": "low"}
                                ],
                                related_data=[doc, ticket],
                                generated_at=datetime.utcnow(),
                                services_involved=[IntegrationType.GOOGLE_DRIVE, IntegrationType.ZENDESK]
                            )
                            insights.append(insight)
            
            # Correlate financial data and support
            if quickbooks_data and zendesk_data:
                high_value_invoices = [i for i in quickbooks_data if i.metadata.get('total', 0) > 5000]
                high_priority_tickets = [t for t in zendesk_data if 'urgent' in t.tags or 'high' in t.tags]
                
                if high_value_invoices and high_priority_tickets:
                    insight = CrossServiceInsight(
                        insight_id=str(uuid.uuid4()),
                        insight_type="correlation",
                        title="High-Value Customers with Support Issues",
                        description=f"{len(high_priority_tickets)} high-priority support tickets from customers with {len(high_value_invoices)} high-value invoices",
                        confidence_score=0.7,
                        business_impact="Risk of customer retention issues with valuable clients",
                        action_items=[
                            {"action": "Prioritize support for high-value customers", "priority": "high"},
                            {"action": "Review contract terms and SLA compliance", "priority": "medium"},
                            {"action": "Proactive outreach to ensure satisfaction", "priority": "medium"}
                        ],
                        related_data=high_value_invoices[:3] + high_priority_tickets[:3],
                        generated_at=datetime.utcnow(),
                        services_involved=[IntegrationType.QUICKBOOKS, IntegrationType.ZENDESK]
                    )
                    insights.append(insight)
            
        except Exception as e:
            logger.error(f"Error generating correlation insights: {e}")
        
        return insights
    
    async def _generate_efficiency_insights(self, service_data: List[ServiceData]) -> List[CrossServiceInsight]:
        """Generate efficiency-based insights"""
        insights = []
        
        try:
            # Analyze efficiency across services
            service_data_by_type = {}
            for data in service_data:
                service_type = data.service_type
                if service_type not in service_data_by_type:
                    service_data_by_type[service_type] = []
                service_data_by_type[service_type].append(data)
            
            # Check for potential automation opportunities
            for service_type, data_list in service_data_by_type.items():
                if len(data_list) < 5:
                    continue
                
                # Look for repetitive patterns
                title_words = {}
                for data in data_list:
                    for word in data.title.lower().split():
                        if len(word) > 3:  # Skip short words
                            title_words[word] = title_words.get(word, 0) + 1
                
                # Find common patterns
                common_words = [word for word, count in title_words.items() if count >= 3]
                
                if common_words and service_type == IntegrationType.ZENDESK:
                    insight = CrossServiceInsight(
                        insight_id=str(uuid.uuid4()),
                        insight_type="efficiency",
                        title="Repetitive Support Ticket Patterns Identified",
                        description=f"Support tickets show repetitive patterns: {', '.join(common_words[:5])}",
                        confidence_score=0.8,
                        business_impact="Opportunity for automation through templates and self-service",
                        action_items=[
                            {"action": "Create support templates for common issues", "priority": "medium"},
                            {"action": "Develop knowledge base articles", "priority": "medium"},
                            {"action": "Implement automated responses for simple queries", "priority": "low"}
                        ],
                        related_data=data_list[:5],
                        generated_at=datetime.utcnow(),
                        services_involved=[IntegrationType.ZENDESK]
                    )
                    insights.append(insight)
            
        except Exception as e:
            logger.error(f"Error generating efficiency insights: {e}")
        
        return insights
    
    async def _generate_opportunity_insights(self, service_data: List[ServiceData]) -> List[CrossServiceInsight]:
        """Generate opportunity-based insights"""
        insights = []
        
        try:
            # Look for business opportunities
            google_drive_data = [d for d in service_data if d.service_type == IntegrationType.GOOGLE_DRIVE]
            hubspot_data = [d for d in service_data if d.service_type == IntegrationType.HUBSPOT]
            
            # Look for proposal documents and opportunities
            proposals = [d for d in google_drive_data if any('proposal' in tag.lower() or 'quote' in tag.lower() for tag in d.tags)]
            opportunities = [d for d in hubspot_data if 'opportunity' in d.tags]
            
            if len(proposals) > 3 and len(opportunities) < 3:
                insight = CrossServiceInsight(
                    insight_id=str(uuid.uuid4()),
                    insight_type="opportunity",
                    title="Proposal Activity Without CRM Opportunities",
                    description=f"Found {len(proposals)} proposal documents but only {len(opportunities)} opportunities in CRM",
                    confidence_score=0.7,
                    business_impact="Potential sales opportunities not being properly tracked in CRM",
                    action_items=[
                        {"action": "Review proposal documents for missing opportunities", "priority": "high"},
                        {"action": "Ensure all proposals have corresponding CRM records", "priority": "medium"},
                        {"action": "Implement workflow to auto-create opportunities from proposals", "priority": "medium"}
                    ],
                    related_data=proposals[:5],
                    generated_at=datetime.utcnow(),
                    services_involved=[IntegrationType.GOOGLE_DRIVE, IntegrationType.HUBSPOT]
                )
                insights.append(insight)
            
        except Exception as e:
            logger.error(f"Error generating opportunity insights: {e}")
        
        return insights
    
    async def recommend_workflows(self, service_data: Optional[List[ServiceData]] = None) -> List[WorkflowRecommendation]:
        """Generate AI-powered workflow recommendations"""
        try:
            if service_data is None:
                service_data = self.service_data
            
            if not service_data:
                logger.warning("No service data available for workflow recommendations")
                return []
            
            recommendations = []
            
            # Generate workflow recommendations based on patterns
            recommendations.extend(await self._generate_cross_service_workflows(service_data))
            recommendations.extend(await self._generate_automation_workflows(service_data))
            
            # Store recommendations
            self.workflows = recommendations
            
            logger.info(f"Generated {len(recommendations)} workflow recommendations")
            return recommendations
            
        except Exception as e:
            logger.error(f"Failed to generate workflow recommendations: {e}")
            return []
    
    async def _generate_cross_service_workflows(self, service_data: List[ServiceData]) -> List[WorkflowRecommendation]:
        """Generate cross-service workflow recommendations"""
        recommendations = []
        
        try:
            # Document to Support workflow
            google_drive_data = [d for d in service_data if d.service_type == IntegrationType.GOOGLE_DRIVE]
            zendesk_data = [d for d in service_data if d.service_type == IntegrationType.ZENDESK]
            
            if google_drive_data and zendesk_data:
                recommendation = WorkflowRecommendation(
                    workflow_id=str(uuid.uuid4()),
                    workflow_name="Document Issue to Support Ticket",
                    description="Automatically create support tickets when document issues are detected",
                    trigger_condition="Document categorized as 'Issue' or contains complaint keywords",
                    services=[IntegrationType.GOOGLE_DRIVE, IntegrationType.ZENDESK],
                    steps=[
                        {"service": "Google Drive", "action": "Monitor new documents for issues", "description": "Watch for documents with issue-related tags or content"},
                        {"service": "Document Intelligence", "action": "Analyze document for problem indicators", "description": "Use AI to detect potential issues in documents"},
                        {"service": "Zendesk", "action": "Create support ticket", "description": "Automatically create ticket with document reference"},
                        {"service": "Notification", "action": "Alert relevant team", "description": "Notify appropriate team about the issue"}
                    ],
                    expected_benefit="30% faster issue detection and resolution, improved customer satisfaction",
                    confidence_score=0.8,
                    priority="high"
                )
                recommendations.append(recommendation)
            
            # Invoice to Notification workflow
            quickbooks_data = [d for d in service_data if d.service_type == IntegrationType.QUICKBOOKS]
            hubspot_data = [d for d in service_data if d.service_type == IntegrationType.HUBSPOT]
            
            if quickbooks_data and hubspot_data:
                recommendation = WorkflowRecommendation(
                    workflow_id=str(uuid.uuid4()),
                    workflow_name="High-Value Invoice Alert",
                    description="Alert sales team when high-value invoices are created",
                    trigger_condition="Invoice total exceeds $10,000",
                    services=[IntegrationType.QUICKBOOKS, IntegrationType.HUBSPOT],
                    steps=[
                        {"service": "QuickBooks", "action": "Monitor new invoices", "description": "Watch for new high-value invoices"},
                        {"service": "HubSpot", "action": "Update contact record", "description": "Add invoice activity to customer CRM record"},
                        {"service": "Notification", "action": "Alert sales team", "description": "Send alert to account manager"},
                        {"service": "CRM", "action": "Schedule follow-up", "description": "Schedule customer check-in"}
                    ],
                    expected_benefit="20% improved customer retention, proactive account management",
                    confidence_score=0.7,
                    priority="medium"
                )
                recommendations.append(recommendation)
            
        except Exception as e:
            logger.error(f"Error generating cross-service workflows: {e}")
        
        return recommendations
    
    async def _generate_automation_workflows(self, service_data: List[ServiceData]) -> List[WorkflowRecommendation]:
        """Generate automation workflow recommendations"""
        recommendations = []
        
        try:
            # Automated categorization workflow
            google_drive_data = [d for d in service_data if d.service_type == IntegrationType.GOOGLE_DRIVE]
            
            if google_drive_data:
                uncategorized_docs = [d for d in google_drive_data if not d.tags or len(d.tags) == 0]
                
                if len(uncategorized_docs) > 5:
                    recommendation = WorkflowRecommendation(
                        workflow_id=str(uuid.uuid4()),
                        workflow_name="Automated Document Categorization",
                        description="Automatically categorize and tag uncategorized documents using AI",
                        trigger_condition="New document uploaded without tags or category",
                        services=[IntegrationType.GOOGLE_DRIVE],
                        steps=[
                            {"service": "Google Drive", "action": "Monitor new uploads", "description": "Watch for new document uploads"},
                            {"service": "Document Intelligence", "action": "Analyze document content", "description": "Use AI to analyze and categorize document"},
                            {"service": "Google Drive", "action": "Apply tags and move to folder", "description": "Automatically categorize and organize"},
                            {"service": "Notification", "action": "Alert document owner", "description": "Notify about automated categorization"}
                        ],
                        expected_benefit="50% faster document organization, improved search and discovery",
                        confidence_score=0.9,
                        priority="high"
                    )
                    recommendations.append(recommendation)
            
        except Exception as e:
            logger.error(f"Error generating automation workflows: {e}")
        
        return recommendations
    
    async def predict_business_trends(self, service_data: Optional[List[ServiceData]] = None) -> List[BusinessPrediction]:
        """Generate AI-powered business predictions"""
        try:
            if service_data is None:
                service_data = self.service_data
            
            if not service_data:
                logger.warning("No service data available for predictions")
                return []
            
            predictions = []
            
            # Generate different types of predictions
            predictions.extend(await self._generate_workload_predictions(service_data))
            predictions.extend(await self._generate_financial_predictions(service_data))
            predictions.extend(await self._generate_customer_behavior_predictions(service_data))
            
            logger.info(f"Generated {len(predictions)} business predictions")
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to generate business predictions: {e}")
            return []
    
    async def _generate_workload_predictions(self, service_data: List[ServiceData]) -> List[BusinessPrediction]:
        """Generate workload-based predictions"""
        predictions = []
        
        try:
            # Analyze support ticket trends
            zendesk_data = [d for d in service_data if d.service_type == IntegrationType.ZENDESK]
            
            if len(zendesk_data) > 7:
                # Calculate recent trend
                recent_tickets = sorted(zendesk_data, key=lambda x: x.timestamp, reverse=True)[:7]
                older_tickets = sorted(zendesk_data, key=lambda x: x.timestamp, reverse=True)[7:14]
                
                recent_high_priority = len([d for d in recent_tickets if 'urgent' in d.tags or 'high' in d.tags])
                older_high_priority = len([d for d in older_tickets if 'urgent' in d.tags or 'high' in d.tags])
                
                # Predict future workload
                if recent_high_priority > older_high_priority:
                    predicted_increase = ((recent_high_priority / older_high_priority - 1) * 100) if older_high_priority > 0 else 50
                    
                    prediction = BusinessPrediction(
                        prediction_id=str(uuid.uuid4()),
                        prediction_type="workload",
                        title="Support Workload Increase Predicted",
                        prediction=f"Support team workload likely to increase by {predicted_increase:.1f}% in next 2 weeks",
                        confidence_interval=(predicted_increase * 0.7, predicted_increase * 1.3),
                        influencing_factors=[
                            {"factor": "High-priority ticket trend", "impact": "High"},
                            {"factor": "Recent ticket volume", "impact": "Medium"}
                        ],
                        business_impact="Potential need for additional staffing or process improvements",
                        timeline="2 weeks",
                        generated_at=datetime.utcnow(),
                        services_involved=[IntegrationType.ZENDESK]
                    )
                    predictions.append(prediction)
            
        except Exception as e:
            logger.error(f"Error generating workload predictions: {e}")
        
        return predictions
    
    async def _generate_financial_predictions(self, service_data: List[ServiceData]) -> List[BusinessPrediction]:
        """Generate financial-based predictions"""
        predictions = []
        
        try:
            # Analyze invoice trends
            quickbooks_data = [d for d in service_data if d.service_type == IntegrationType.QUICKBOOKS]
            
            if len(quickbooks_data) > 5:
                # Calculate revenue trend
                recent_invoices = sorted(quickbooks_data, key=lambda x: x.timestamp, reverse=True)[:5]
                total_recent = sum(d.metadata.get('total', 0) for d in recent_invoices)
                
                # Predict monthly revenue
                avg_invoice = total_recent / len(recent_invoices) if recent_invoices else 0
                predicted_monthly = avg_invoice * len(recent_invoices) * 4  # Assuming similar rate
                
                prediction = BusinessPrediction(
                    prediction_id=str(uuid.uuid4()),
                    prediction_type="financial",
                    title="Monthly Revenue Projection",
                    prediction=f"Monthly revenue likely to be around ${predicted_monthly:,.2f} based on current trends",
                    confidence_interval=(predicted_monthly * 0.8, predicted_monthly * 1.2),
                    influencing_factors=[
                        {"factor": "Recent invoice volume", "impact": "High"},
                        {"factor": "Average invoice value", "impact": "High"}
                    ],
                    business_impact="Helps with financial planning and resource allocation",
                    timeline="1 month",
                    generated_at=datetime.utcnow(),
                    services_involved=[IntegrationType.QUICKBOOKS]
                )
                predictions.append(prediction)
            
        except Exception as e:
            logger.error(f"Error generating financial predictions: {e}")
        
        return predictions
    
    async def _generate_customer_behavior_predictions(self, service_data: List[ServiceData]) -> List[BusinessPrediction]:
        """Generate customer behavior predictions"""
        predictions = []
        
        try:
            # Analyze support and financial data for churn risk
            zendesk_data = [d for d in service_data if d.service_type == IntegrationType.ZENDESK]
            quickbooks_data = [d for d in service_data if d.service_type == IntegrationType.QUICKBOOKS]
            
            # Find customers with high support activity and high-value invoices
            if zendesk_data and quickbooks_data:
                high_activity_customers = []
                
                # This is simplified - in production would match by customer ID
                high_priority_tickets = len([d for d in zendesk_data if 'urgent' in d.tags or 'high' in d.tags])
                high_value_invoices = len([d for d in quickbooks_data if d.metadata.get('total', 0) > 5000])
                
                if high_priority_tickets > 3 and high_value_invoices > 0:
                    prediction = BusinessPrediction(
                        prediction_id=str(uuid.uuid4()),
                        prediction_type="customer_behavior",
                        title="Customer Retention Risk Identified",
                        prediction=f"High-value customers showing increased support activity may indicate retention risk",
                        confidence_interval=(0.6, 0.9),
                        influencing_factors=[
                            {"factor": "Increased support activity", "impact": "High"},
                            {"factor": "High-value account status", "impact": "High"}
                        ],
                        business_impact="Proactive retention actions could prevent customer loss",
                        timeline="1 month",
                        generated_at=datetime.utcnow(),
                        services_involved=[IntegrationType.ZENDESK, IntegrationType.QUICKBOOKS]
                    )
                    predictions.append(prediction)
            
        except Exception as e:
            logger.error(f"Error generating customer behavior predictions: {e}")
        
        return predictions
    
    def get_service_capabilities(self) -> Dict[str, Any]:
        """Get cross-service AI capabilities"""
        return {
            "service": "cross_service_ai",
            "available_services": list(self.services.keys()),
            "ai_capabilities": {
                "data_collection": True,
                "insight_generation": True,
                "workflow_recommendation": True,
                "business_prediction": True,
                "cross_service_analysis": True,
                "trend_detection": True,
                "correlation_analysis": True,
                "efficiency_optimization": True
            },
            "supported_integrations": [t.value for t in IntegrationType],
            "knowledge_graph": self.knowledge_graph is not None,
            "semantic_search": self.sentence_model is not None,
            "ml_models": {
                "tfidf_vectorizer": self.tfidf_vectorizer is not None,
                "sentence_transformer": self.sentence_model is not None,
                "network_analysis": nx is not None
            },
            "data_sources": {
                "google_drive": IntegrationType.GOOGLE_DRIVE in self.services,
                "zendesk": IntegrationType.ZENDESK in self.services,
                "quickbooks": IntegrationType.QUICKBOOKS in self.services,
                "hubspot": IntegrationType.HUBSPOT in self.services
            }
        }

# Factory function
def create_cross_service_ai_service(openai_api_key: Optional[str] = None) -> CrossServiceAIService:
    """Create cross-service AI service instance"""
    return CrossServiceAIService(openai_api_key)