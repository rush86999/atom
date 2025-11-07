"""
ATOM AI Chat Integration Service
Connects Cross-Service AI with main chat interface
Natural language processing for business intelligence queries
"""

import os
import json
import asyncio
import aiohttp
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
from dataclasses import dataclass
from loguru import logger

# Cross-Service AI
from cross_service_ai_service import (
    create_cross_service_ai_service,
    IntegrationType,
    CrossServiceInsight,
    WorkflowRecommendation,
    BusinessPrediction
)

# Document Intelligence
from document_intelligence_service import create_document_intelligence_service

@dataclass
class ChatResponse:
    """Structured chat response for AI queries"""
    response_id: str
    message: str
    response_type: str
    confidence: float
    data: Optional[Dict[str, Any]] = None
    actions: Optional[List[Dict[str, Any]]] = None
    follow_up_questions: Optional[List[str]] = None
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()
        if self.actions is None:
            self.actions = []
        if self.follow_up_questions is None:
            self.follow_up_questions = []

@dataclass
class ChatContext:
    """Chat conversation context"""
    conversation_id: str
    user_id: str
    messages: List[Dict[str, Any]]
    active_services: List[IntegrationType]
    preferences: Dict[str, Any]
    last_query_time: datetime
    
    def __post_init__(self):
        if self.messages is None:
            self.messages = []
        if self.active_services is None:
            self.active_services = []
        if self.preferences is None:
            self.preferences = {}

class ATOMChatAIService:
    """Main AI chat interface service for ATOM platform"""
    
    def __init__(self, openai_api_key: Optional[str] = None):
        self.openai_api_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        
        # Initialize services
        self.cross_service_ai = create_cross_service_ai_service(openai_api_key)
        self.document_intelligence = create_document_intelligence_service(openai_api_key)
        
        # Chat contexts (in production, would be database)
        self.contexts = {}  # conversation_id -> ChatContext
        
        # Intent classifiers
        self.intent_patterns = {
            'insight': [
                'what insights', 'any insights', 'show insights', 'business insights',
                'performance', 'trends', 'analytics', 'patterns', 'issues'
            ],
            'workflow': [
                'workflow', 'automation', 'automate', 'recommend', 'suggestions',
                'improve efficiency', 'optimize', 'streamline'
            ],
            'prediction': [
                'predict', 'forecast', 'prediction', 'future', 'expect',
                'trend prediction', 'business prediction', 'outlook'
            ],
            'search': [
                'search', 'find', 'look for', 'show me', 'get me',
                'documents', 'tickets', 'invoices', 'contacts', 'reports'
            ],
            'compare': [
                'compare', 'difference', 'versus', 'vs', 'relationship',
                'correlation', 'connection', 'how does relate'
            ],
            'action': [
                'create', 'update', 'delete', 'move', 'send', 'notify',
                'trigger', 'execute', 'run', 'start', 'stop'
            ],
            'help': [
                'help', 'how to', 'what can', 'explain', 'guide',
                'tutorial', 'assist', 'support', 'instructions'
            ]
        }
        
        logger.info("ATOM Chat AI Service initialized")
    
    async def process_query(self, query: str, user_id: str, conversation_id: Optional[str] = None, 
                          access_tokens: Optional[Dict[str, str]] = None) -> ChatResponse:
        """Process user query and generate AI response"""
        try:
            # Get or create conversation context
            if conversation_id:
                context = self.contexts.get(conversation_id)
                if not context:
                    context = self._create_context(conversation_id, user_id)
            else:
                conversation_id = self._generate_conversation_id()
                context = self._create_context(conversation_id, user_id)
            
            # Add user message to context
            context.messages.append({
                'type': 'user',
                'content': query,
                'timestamp': datetime.utcnow(),
                'message_id': self._generate_message_id()
            })
            
            # Update context
            context.last_query_time = datetime.utcnow()
            self.contexts[conversation_id] = context
            
            # Process query based on intent
            intent, confidence = self._classify_intent(query)
            logger.info(f"Query classified with intent: {intent} (confidence: {confidence:.2f})")
            
            # Generate response based on intent
            if intent == 'insight':
                response = await self._handle_insight_query(query, context, access_tokens)
            elif intent == 'workflow':
                response = await self._handle_workflow_query(query, context, access_tokens)
            elif intent == 'prediction':
                response = await self._handle_prediction_query(query, context, access_tokens)
            elif intent == 'search':
                response = await self._handle_search_query(query, context, access_tokens)
            elif intent == 'compare':
                response = await self._handle_compare_query(query, context, access_tokens)
            elif intent == 'action':
                response = await self._handle_action_query(query, context, access_tokens)
            elif intent == 'help':
                response = await self._handle_help_query(query, context, access_tokens)
            else:
                response = await self._handle_general_query(query, context, access_tokens)
            
            # Add AI message to context
            context.messages.append({
                'type': 'ai',
                'content': response.message,
                'timestamp': response.timestamp,
                'message_id': self._generate_message_id(),
                'response_type': response.response_type,
                'data': response.data,
                'actions': response.actions
            })
            
            return response
            
        except Exception as e:
            logger.error(f"Error processing query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I apologize, but I encountered an error while processing your request. Please try again or contact support.",
                response_type="error",
                confidence=0.0,
                timestamp=datetime.utcnow()
            )
    
    def _create_context(self, conversation_id: str, user_id: str) -> ChatContext:
        """Create new chat context"""
        return ChatContext(
            conversation_id=conversation_id,
            user_id=user_id,
            messages=[],
            active_services=list(IntegrationType),
            preferences={},
            last_query_time=datetime.utcnow()
        )
    
    def _generate_conversation_id(self) -> str:
        """Generate unique conversation ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _generate_message_id(self) -> str:
        """Generate unique message ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _generate_response_id(self) -> str:
        """Generate unique response ID"""
        import uuid
        return str(uuid.uuid4())
    
    def _classify_intent(self, query: str) -> Tuple[str, float]:
        """Classify user query intent"""
        query_lower = query.lower()
        best_intent = 'general'
        best_confidence = 0.0
        
        for intent, patterns in self.intent_patterns.items():
            confidence = 0.0
            matches = 0
            
            for pattern in patterns:
                if pattern in query_lower:
                    matches += 1
                    # Full match gets higher confidence
                    if pattern == query_lower:
                        confidence = 1.0
                    else:
                        confidence += 0.5
            
            if matches > 0:
                confidence = min(1.0, confidence / len(patterns))
                if confidence > best_confidence:
                    best_confidence = confidence
                    best_intent = intent
        
        return best_intent, best_confidence
    
    async def _handle_insight_query(self, query: str, context: ChatContext, 
                                 access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle insight-related queries"""
        try:
            # Collect recent data if access tokens provided
            if access_tokens:
                service_tokens = {IntegrationType[t]: token for t, token in access_tokens.items() 
                                if t in IntegrationType.__members__}
                await self.cross_service_ai.collect_all_service_data(service_tokens, limit=5)
            
            # Generate insights
            insights = await self.cross_service_ai.generate_cross_service_insights()
            
            if not insights:
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I don't have enough data to generate insights at the moment. Let me collect some data from your services first.",
                    response_type="insight",
                    confidence=0.3,
                    follow_up_questions=[
                        "Would you like me to collect data from your integrations?",
                        "Which services would you like me to analyze?"
                    ]
                )
            
            # Format insights for chat
            insight_text = f"I found {len(insights)} business insights:\n\n"
            
            for i, insight in enumerate(insights[:3], 1):
                insight_text += f"**{i}. {insight.title}**\n"
                insight_text += f"{insight.description}\n"
                if insight.business_impact:
                    insight_text += f"*Business Impact:* {insight.business_impact}\n"
                if insight.action_items:
                    actions_text = ", ".join([f"'{item['action']}'" for item in insight.action_items[:2]])
                    insight_text += f"*Suggested Actions:* {actions_text}\n"
                insight_text += "\n"
            
            # Create actions
            actions = []
            for insight in insights[:3]:
                actions.append({
                    "type": "view_insight",
                    "text": f"View '{insight.title}'",
                    "data": {"insight_id": insight.insight_id}
                })
            
            return ChatResponse(
                response_id=self._generate_response_id(),
                message=insight_text,
                response_type="insight",
                confidence=0.8,
                data={
                    "insights_count": len(insights),
                    "insights_preview": [{"id": i.insight_id, "title": i.title} for i in insights[:5]]
                },
                actions=actions,
                follow_up_questions=[
                    "Show me more details about these insights",
                    "What actions should I take based on these insights?",
                    "How can I prevent these issues in the future?"
                ]
            )
            
        except Exception as e:
            logger.error(f"Error handling insight query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I had trouble generating insights. Let me try a different approach.",
                response_type="error",
                confidence=0.0
            )
    
    async def _handle_workflow_query(self, query: str, context: ChatContext, 
                                  access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle workflow-related queries"""
        try:
            # Collect data and generate recommendations
            if access_tokens:
                service_tokens = {IntegrationType[t]: token for t, token in access_tokens.items() 
                                if t in IntegrationType.__members__}
                await self.cross_service_ai.collect_all_service_data(service_tokens, limit=5)
            
            workflows = await self.cross_service_ai.recommend_workflows()
            
            if not workflows:
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I don't have enough data to recommend workflows yet. Let me analyze your current processes.",
                    response_type="workflow",
                    confidence=0.3,
                    follow_up_questions=[
                        "Which processes would you like me to automate?",
                        "What's taking most of your team's time?"
                    ]
                )
            
            # Format workflow recommendations
            workflow_text = f"I found {len(workflows)} workflow optimization opportunities:\n\n"
            
            for i, workflow in enumerate(workflows[:3], 1):
                workflow_text += f"**{i}. {workflow.workflow_name}**\n"
                workflow_text += f"{workflow.description}\n"
                if workflow.expected_benefit:
                    workflow_text += f"*Expected Benefit:* {workflow.expected_benefit}\n"
                if workflow.priority:
                    workflow_text += f"*Priority:* {workflow.priority.upper()}\n"
                workflow_text += "\n"
            
            # Create actions
            actions = []
            for workflow in workflows[:3]:
                actions.append({
                    "type": "implement_workflow",
                    "text": f"Implement '{workflow.workflow_name}'",
                    "data": {"workflow_id": workflow.workflow_id}
                })
            
            return ChatResponse(
                response_id=self._generate_response_id(),
                message=workflow_text,
                response_type="workflow",
                confidence=0.8,
                data={
                    "workflows_count": len(workflows),
                    "workflows_preview": [{"id": w.workflow_id, "name": w.workflow_name, "priority": w.priority} for w in workflows[:5]]
                },
                actions=actions,
                follow_up_questions=[
                    "Show me detailed steps for implementing these workflows",
                    "Which workflow should I implement first?",
                    "How much time will these workflows save?"
                ]
            )
            
        except Exception as e:
            logger.error(f"Error handling workflow query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I had trouble generating workflow recommendations. Let me try again with more specific information.",
                response_type="error",
                confidence=0.0
            )
    
    async def _handle_prediction_query(self, query: str, context: ChatContext, 
                                   access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle prediction-related queries"""
        try:
            # Collect data and generate predictions
            if access_tokens:
                service_tokens = {IntegrationType[t]: token for t, token in access_tokens.items() 
                                if t in IntegrationType.__members__}
                await self.cross_service_ai.collect_all_service_data(service_tokens, limit=5)
            
            predictions = await self.cross_service_ai.predict_business_trends()
            
            if not predictions:
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I need more historical data to make accurate predictions. Let me collect and analyze more information from your services.",
                    response_type="prediction",
                    confidence=0.3,
                    follow_up_questions=[
                        "What time period would you like me to predict?",
                        "Which business metrics are most important to you?"
                    ]
                )
            
            # Format predictions
            prediction_text = f"Based on current trends, here are my predictions:\n\n"
            
            for i, prediction in enumerate(predictions[:3], 1):
                prediction_text += f"**{i}. {prediction.title}**\n"
                prediction_text += f"{prediction.prediction}\n"
                if prediction.confidence_interval:
                    lower, upper = prediction.confidence_interval
                    prediction_text += f"*Confidence Interval:* {lower:.1%} - {upper:.1%}\n"
                if prediction.timeline:
                    prediction_text += f"*Timeline:* {prediction.timeline}\n"
                if prediction.business_impact:
                    prediction_text += f"*Business Impact:* {prediction.business_impact}\n"
                prediction_text += "\n"
            
            # Create actions
            actions = []
            for prediction in predictions[:3]:
                actions.append({
                    "type": "monitor_prediction",
                    "text": f"Monitor '{prediction.title}'",
                    "data": {"prediction_id": prediction.prediction_id}
                })
            
            return ChatResponse(
                response_id=self._generate_response_id(),
                message=prediction_text,
                response_type="prediction",
                confidence=0.7,
                data={
                    "predictions_count": len(predictions),
                    "predictions_preview": [{"id": p.prediction_id, "title": p.title, "timeline": p.timeline} for p in predictions[:5]]
                },
                actions=actions,
                follow_up_questions=[
                    "How can I prepare for these predictions?",
                    "What's influencing these predictions?",
                    "Show me the detailed analysis behind these predictions"
                ]
            )
            
        except Exception as e:
            logger.error(f"Error handling prediction query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I had trouble generating predictions. Let me collect more data to improve accuracy.",
                response_type="error",
                confidence=0.0
            )
    
    async def _handle_search_query(self, query: str, context: ChatContext, 
                                access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle search-related queries"""
        try:
            # Parse search intent
            search_terms = []
            target_service = None
            
            query_lower = query.lower()
            
            # Identify target service
            if any(term in query_lower for term in ['document', 'file', 'drive', 'doc']):
                target_service = IntegrationType.GOOGLE_DRIVE
            elif any(term in query_lower for term in ['ticket', 'support', 'zendesk', 'issue']):
                target_service = IntegrationType.ZENDESK
            elif any(term in query_lower for term in ['invoice', 'payment', 'quickbooks', 'financial']):
                target_service = IntegrationType.QUICKBOOKS
            elif any(term in query_lower for term in ['contact', 'customer', 'hubspot', 'crm']):
                target_service = IntegrationType.HUBSPOT
            
            # Extract search terms
            words = query.split()
            for word in words:
                if word.lower() not in ['search', 'find', 'show', 'me', 'get', 'look', 'for', 'in', 'the']:
                    search_terms.append(word)
            
            if not target_service and not search_terms:
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I can help you search across your integrations! Please specify what you're looking for and which service to search.",
                    response_type="search",
                    confidence=0.5,
                    follow_up_questions=[
                        "Which service would you like to search? (Google Drive, Zendesk, QuickBooks, HubSpot)",
                        "What are you looking for?",
                        "Can you be more specific about your search criteria?"
                    ]
                )
            
            # Perform search (mock implementation)
            search_results = []
            
            if target_service and access_tokens and target_service.value in access_tokens:
                # This would use actual service search in production
                service_name = target_service.value.replace('_', ' ').title()
                search_results = [
                    {
                        "id": "mock_id_1",
                        "title": f"Sample {target_service.value} result 1",
                        "description": f"Mock search result for {' '.join(search_terms)} in {service_name}",
                        "service": service_name,
                        "url": "#mock-url-1"
                    },
                    {
                        "id": "mock_id_2", 
                        "title": f"Sample {target_service.value} result 2",
                        "description": f"Another mock result matching your search terms",
                        "service": service_name,
                        "url": "#mock-url-2"
                    }
                ]
            
            # Format search results
            if search_results:
                result_text = f"I found {len(search_results)} results"
                if target_service:
                    result_text += f" in {target_service.value.replace('_', ' ').title()}"
                result_text += ":\n\n"
                
                for i, result in enumerate(search_results[:5], 1):
                    result_text += f"**{i}. {result['title']}**\n"
                    result_text += f"*{result['description']}*\n"
                    result_text += f"*Service:* {result['service']}\n"
                    result_text += "\n"
            else:
                result_text = f"I didn't find any results for your search."
                if target_service:
                    result_text += f" Try searching in {target_service.value.replace('_', ' ').title()} or use different terms."
            
            # Create actions
            actions = []
            for result in search_results:
                actions.append({
                    "type": "open_result",
                    "text": f"Open '{result['title']}'",
                    "data": {"url": result['url'], "id": result['id']}
                })
            
            return ChatResponse(
                response_id=self._generate_response_id(),
                message=result_text,
                response_type="search",
                confidence=0.8,
                data={
                    "search_results_count": len(search_results),
                    "search_results": search_results,
                    "searched_service": target_service.value if target_service else None
                },
                actions=actions,
                follow_up_questions=[
                    "Refine search results",
                    "Search in a different service",
                    "Help me understand these results"
                ]
            )
            
        except Exception as e:
            logger.error(f"Error handling search query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I had trouble searching. Could you please provide more specific search criteria?",
                response_type="error",
                confidence=0.0
            )
    
    async def _handle_compare_query(self, query: str, context: ChatContext, 
                                 access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle comparison queries"""
        try:
            # Parse comparison intent
            query_lower = query.lower()
            
            # Look for comparison patterns
            if any(term in query_lower for term in ['support', 'ticket', 'zendesk']) and \
               any(term in query_lower for term in ['document', 'file', 'drive']):
                
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I can compare your support tickets with related documents! This helps identify documentation gaps and knowledge base improvements.\n\n**Key Correlations:**\n• Tickets often reference outdated documents\n• Documentation quality affects ticket volume\n• Better documentation reduces support workload\n\n**Recommendations:**\n• Update frequently referenced documents\n• Create knowledge base articles from common issues\n• Link tickets to relevant documentation",
                    response_type="compare",
                    confidence=0.7,
                    data={
                        "comparison_type": "support_vs_documents",
                        "key_findings": [
                            "Documentation quality impacts support volume",
                            "Tickets often reference outdated information", 
                            "Opportunity for knowledge base improvements"
                        ]
                    },
                    actions=[
                        {"type": "view_correlation", "text": "See ticket-document correlations"},
                        {"type": "improve_docs", "text": "Improve documentation quality"}
                    ]
                )
            
            elif any(term in query_lower for term in ['invoice', 'payment', 'quickbooks']) and \
                 any(term in query_lower for term in ['customer', 'contact', 'hubspot']):
                
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I can compare your financial data with customer information! This helps identify high-value customers and payment patterns.\n\n**Key Insights:**\n• High-value customers often have different support needs\n• Payment patterns correlate with customer satisfaction\n• CRM data helps predict financial outcomes\n\n**Business Impact:**\n• Better customer segmentation\n• Improved cash flow management\n• More targeted customer support",
                    response_type="compare", 
                    confidence=0.7,
                    data={
                        "comparison_type": "financial_vs_customers",
                        "key_findings": [
                            "High-value customers require different support levels",
                            "Payment patterns indicate customer satisfaction",
                            "CRM integration improves financial predictions"
                        ]
                    },
                    actions=[
                        {"type": "customer_analysis", "text": "Analyze customer value"},
                        {"type": "payment_trends", "text": "Review payment patterns"}
                    ]
                )
            
            else:
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I can compare data across your integrations! For example:\n• Support tickets vs related documents\n• Financial data vs customer information\n• Marketing campaigns vs sales results\n\nWhich comparison would be most helpful?",
                    response_type="compare",
                    confidence=0.5,
                    follow_up_questions=[
                        "Compare support tickets with documents?",
                        "Analyze financial data with customer information?",
                        "Examine marketing vs sales correlation?"
                    ]
                )
                
        except Exception as e:
            logger.error(f"Error handling compare query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I can help you compare data across services. Which aspects would you like me to analyze?",
                response_type="compare",
                confidence=0.5
            )
    
    async def _handle_action_query(self, query: str, context: ChatContext, 
                                access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle action-related queries"""
        try:
            query_lower = query.lower()
            
            # Document actions
            if any(term in query_lower for term in ['document', 'file', 'drive']):
                if any(term in query_lower for term in ['analyze', 'categorize', 'organize']):
                    return ChatResponse(
                        response_id=self._generate_response_id(),
                        message="I can analyze and organize your documents using AI! I'll:\n• Categorize documents by content and purpose\n• Extract keywords and entities\n• Identify important documents\n• Suggest organizational structure\n• Check for compliance issues\n\nWould you like me to analyze all documents or specific ones?",
                        response_type="action",
                        confidence=0.8,
                        data={"action_type": "document_analysis"},
                        actions=[
                            {"type": "analyze_all_docs", "text": "Analyze all documents"},
                            {"type": "analyze_specific_docs", "text": "Analyze specific documents"}
                        ]
                    )
            
            # Support actions
            elif any(term in query_lower for term in ['ticket', 'support', 'zendesk']):
                if any(term in query_lower for term in ['create', 'new', 'escalate']):
                    return ChatResponse(
                        response_id=self._generate_response_id(),
                        message="I can help you create and manage support tickets! I can:\n• Create new tickets automatically from issues\n• Escalate high-priority tickets\n• Assign tickets based on content\n• Generate ticket summaries\n• Follow up on unresolved tickets\n\nWhat type of support action would you like me to perform?",
                        response_type="action",
                        confidence=0.8,
                        data={"action_type": "support_management"},
                        actions=[
                            {"type": "create_ticket", "text": "Create new ticket"},
                            {"type": "escalate_ticket", "text": "Escalate tickets"},
                            {"type": "review_tickets", "text": "Review ticket queue"}
                        ]
                    )
            
            # General actions
            else:
                return ChatResponse(
                    response_id=self._generate_response_id(),
                    message="I can help you perform actions across your integrations! I can:\n• Analyze and organize documents\n• Create and manage support tickets\n• Process financial data\n• Update customer information\n• Automate workflows\n\nWhich action would you like me to perform?",
                    response_type="action",
                    confidence=0.6,
                    follow_up_questions=[
                        "Analyze documents using AI?",
                        "Manage support tickets automatically?",
                        "Process financial information?",
                        "Update customer records?"
                    ]
                )
                
        except Exception as e:
            logger.error(f"Error handling action query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I can help you perform various actions. Could you be more specific about what you'd like me to do?",
                response_type="action",
                confidence=0.5
            )
    
    async def _handle_help_query(self, query: str, context: ChatContext, 
                              access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle help-related queries"""
        try:
            help_text = """I'm your ATOM AI assistant! I can help you with:

**📊 Business Intelligence**
• Generate insights from your data
• Identify trends and patterns
• Predict business outcomes
• Recommend optimizations

**🔄 Workflow Automation**
• Automate repetitive tasks
• Create intelligent workflows
• Streamline business processes
• Improve efficiency

**🔍 Search & Discovery**
• Find documents, tickets, contacts, invoices
• Semantic search across all services
• Locate related information
• Cross-service data discovery

**⚡ Actions & Operations**
• Analyze documents with AI
• Create support tickets
• Process financial data
• Update customer information
• Execute workflows

**📈 Comparisons & Analysis**
• Compare data across services
• Identify correlations
• Analyze relationships
• Generate business insights

**Just ask me questions like:**
• "What insights can you find?"
• "How can I automate my workflows?"
• "Find customer support tickets"
• "Compare invoices with customer data"
• "Analyze this document for me"

**Connected Services:** Google Drive, Zendesk, QuickBooks, HubSpot

What would you like help with today?"""
            
            return ChatResponse(
                response_id=self._generate_response_id(),
                message=help_text,
                response_type="help",
                confidence=0.9,
                data={
                    "capabilities": [
                        "business_intelligence",
                        "workflow_automation", 
                        "search_discovery",
                        "actions_operations",
                        "comparisons_analysis"
                    ],
                    "connected_services": ["Google Drive", "Zendesk", "QuickBooks", "HubSpot"]
                },
                actions=[
                    {"type": "generate_insights", "text": "Generate Business Insights"},
                    {"type": "recommend_workflows", "text": "Recommend Workflows"},
                    {"type": "search_services", "text": "Search Services"}
                ]
            )
            
        except Exception as e:
            logger.error(f"Error handling help query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I'm here to help! I can assist with business intelligence, workflow automation, search, and actions across your ATOM integrations.",
                response_type="help",
                confidence=0.7
            )
    
    async def _handle_general_query(self, query: str, context: ChatContext, 
                                 access_tokens: Optional[Dict[str, str]]) -> ChatResponse:
        """Handle general queries"""
        try:
            # Try to provide relevant general assistance
            general_text = """I'm here to help you with your ATOM platform! Here's what I can do:

**Get Started:**
• Ask me "What insights can you find?" for business intelligence
• Say "Recommend workflows" for automation suggestions  
• Try "Find documents" to search across services
• Ask "How can I help?" for assistance options

**Quick Examples:**
• "Show me high-priority support tickets"
• "Analyze my financial documents"
• "Predict customer trends"
• "Compare invoice patterns with support issues"

I can analyze data from Google Drive, Zendesk, QuickBooks, and HubSpot to provide intelligent insights and automation recommendations.

What would you like to explore today?"""
            
            return ChatResponse(
                response_id=self._generate_response_id(),
                message=general_text,
                response_type="general",
                confidence=0.6,
                data={
                    "suggestions": [
                        "generate_insights",
                        "recommend_workflows", 
                        "search_services",
                        "predict_trends"
                    ]
                },
                actions=[
                    {"type": "generate_insights", "text": "Generate Business Insights"},
                    {"type": "recommend_workflows", "text": "Recommend Workflows"},
                    {"type": "help", "text": "Show Help Options"}
                ],
                follow_up_questions=[
                    "Generate business insights from your data?",
                    "Find workflow automation opportunities?",
                    "Search across all your services?",
                    "Get specific help with a task?"
                ]
            )
            
        except Exception as e:
            logger.error(f"Error handling general query: {e}")
            return ChatResponse(
                response_id=self._generate_response_id(),
                message="I'm here to help! I can assist with business intelligence, workflow automation, search, and actions across your ATOM integrations. What would you like to explore?",
                response_type="general",
                confidence=0.5
            )
    
    def get_conversation_context(self, conversation_id: str) -> Optional[ChatContext]:
        """Get conversation context"""
        return self.contexts.get(conversation_id)
    
    def update_conversation_preferences(self, conversation_id: str, preferences: Dict[str, Any]) -> bool:
        """Update conversation preferences"""
        if conversation_id in self.contexts:
            self.contexts[conversation_id].preferences.update(preferences)
            return True
        return False
    
    def clear_conversation_context(self, conversation_id: str) -> bool:
        """Clear conversation context"""
        if conversation_id in self.contexts:
            del self.contexts[conversation_id]
            return True
        return False

# Factory function
def create_atom_chat_ai_service(openai_api_key: Optional[str] = None) -> ATOMChatAIService:
    """Create ATOM Chat AI service instance"""
    return ATOMChatAIService(openai_api_key)