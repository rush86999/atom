"""
ATOM AI Enhanced API Routes
Advanced AI-powered endpoints for unified communication ecosystem
"""

import os
import json
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Union
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import AI enhanced services
try:
    from ai_enhanced_service import ai_enhanced_service, AIRequest, AIResponse, AITaskType, AIModelType, AIServiceType
    from atom_ai_integration import atom_ai_integration
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import AtomWorkflowService
    from atom_ingestion_pipeline import AtomIngestionPipeline
except ImportError as e:
    logger.warning(f"AI integration services not available: {e}")
    ai_enhanced_service = None
    atom_ai_integration = None
    AtomMemoryService = None
    AtomSearchService = None
    AtomWorkflowService = None
    AtomIngestionPipeline = None

# Create AI API blueprint
ai_bp = Blueprint('ai_api', __name__, url_prefix='/api/integrations/ai')

# Configuration validation
def validate_ai_config():
    """Validate AI configuration"""
    required_vars = [
        'OPENAI_API_KEY',
        'ANTHROPIC_API_KEY',
        'GOOGLE_AI_API_KEY'
    ]
    
    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)
    
    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False
    
    return True

# Utility functions
def create_ai_response(ok: bool, data: Any = None, error: str = None,
                     message: str = None, metadata: Dict = None) -> Dict[str, Any]:
    """Create standardized AI API response"""
    response = {
        'ok': ok,
        'timestamp': datetime.utcnow().isoformat(),
        'api_version': '5.0.0',
        'service': 'AI Enhanced Integration'
    }
    
    if ok:
        if data is not None:
            response['data'] = data
        if message:
            response['message'] = message
        if metadata:
            response['metadata'] = metadata
    else:
        response['error'] = error or 'Unknown error occurred'
    
    return response

def get_ai_request_data() -> Dict[str, Any]:
    """Get and validate AI request data"""
    try:
        data = request.get_json() or {}
        user_id = data.get('user_id') or request.headers.get('X-User-ID', 'default-user')
        data['user_id'] = user_id
        return data
    except Exception as e:
        logger.error(f"Error parsing AI request data: {e}")
        return {}

def validate_ai_model_type(model_type: str) -> AIModelType:
    """Validate and convert AI model type"""
    try:
        return AIModelType(model_type)
    except ValueError:
        raise ValueError(f"Unsupported model type: {model_type}")

def validate_ai_task_type(task_type: str) -> AITaskType:
    """Validate and convert AI task type"""
    try:
        return AITaskType(task_type)
    except ValueError:
        raise ValueError(f"Unsupported task type: {task_type}")

def validate_ai_service_type(service_type: str) -> AIServiceType:
    """Validate and convert AI service type"""
    try:
        return AIServiceType(service_type)
    except ValueError:
        raise ValueError(f"Unsupported service type: {service_type}")

# AI Service Health Check
@ai_bp.route('/enhanced_health', methods=['POST'])
def ai_enhanced_health_check():
    """Enhanced health check for all AI services"""
    try:
        if not validate_ai_config():
            return create_ai_response(False, error="AI configuration validation failed")
        
        health_status = {
            'ai_enhanced_service': ai_enhanced_service is not None,
            'atom_ai_integration': atom_ai_integration is not None,
            'openai_service': bool(os.getenv('OPENAI_API_KEY')),
            'anthropic_service': bool(os.getenv('ANTHROPIC_API_KEY')),
            'google_ai_service': bool(os.getenv('GOOGLE_AI_API_KEY'))
        }
        
        # Check AI service status
        all_healthy = all(health_status.values())
        
        # Get detailed status if services are available
        service_info = {}
        if ai_enhanced_service:
            service_info['ai_service'] = await ai_enhanced_service.get_service_info()
        if atom_ai_integration:
            service_info['ai_integration'] = {
                'initialized': atom_ai_integration.is_initialized,
                'active_ai_features': len(atom_ai_integration.active_ai_features),
                'intelligent_workspaces': len(atom_ai_integration.intelligent_workspaces)
            }
        
        return create_ai_response(
            all_healthy,
            data={
                'services': health_status,
                'service_info': service_info,
                'status': 'healthy' if all_healthy else 'degraded'
            },
            message="Enhanced AI services operational" if all_healthy else "Some AI services unavailable"
        )
    
    except Exception as e:
        logger.error(f"Enhanced AI health check error: {e}")
        return create_ai_response(False, error=str(e)), 500

# AI Message Analysis
@ai_bp.route('/analyze_message', methods=['POST'])
def analyze_message_ai():
    """Analyze message with AI"""
    try:
        data = get_ai_request_data()
        content = data.get('content')
        platform = data.get('platform')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        analysis_types = data.get('analysis_types', ['sentiment', 'topics'])
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        
        if not content:
            return create_ai_response(False, error="content is required")
        
        if not ai_enhanced_service:
            return create_ai_response(False, error="AI service not available"), 503
        
        # Validate parameters
        try:
            model_type_enum = validate_ai_model_type(model_type)
            service_type_enum = validate_ai_service_type(service_type)
        except ValueError as e:
            return create_ai_response(False, error=str(e)), 400
        
        # Perform analysis
        analysis_results = {}
        
        # Sentiment analysis
        if 'sentiment' in analysis_types:
            sentiment_request = await ai_enhanced_service.process_ai_request(AIRequest(
                request_id=f"sentiment_{int(datetime.utcnow().timestamp())}",
                task_type=AITaskType.SENTIMENT_ANALYSIS,
                model_type=model_type_enum,
                service_type=service_type_enum,
                input_data=content,
                context={
                    'platform': platform,
                    'channel_id': channel_id
                },
                platform=platform,
                user_id=user_id
            ))
            analysis_results['sentiment'] = sentiment_request.output_data if sentiment_request.ok else None
        
        # Topic extraction
        if 'topics' in analysis_types:
            topic_request = await ai_enhanced_service.process_ai_request(AIRequest(
                request_id=f"topics_{int(datetime.utcnow().timestamp())}",
                task_type=AITaskType.TOPIC_EXTRACTION,
                model_type=model_type_enum,
                service_type=service_type_enum,
                input_data=content,
                context={
                    'platform': platform,
                    'channel_id': channel_id
                },
                platform=platform,
                user_id=user_id
            ))
            analysis_results['topics'] = topic_request.output_data if topic_request.ok else None
        
        # Content categorization
        if 'category' in analysis_types:
            category_request = await ai_enhanced_service.process_ai_request(AIRequest(
                request_id=f"category_{int(datetime.utcnow().timestamp())}",
                task_type=AITaskType.CONTENT_GENERATION,
                model_type=model_type_enum,
                service_type=service_type_enum,
                input_data=f"Categorize this content: {content}",
                context={
                    'task': 'content_categorization',
                    'platform': platform
                },
                platform=platform,
                system_prompt="You are an expert content categorization assistant. Provide category and confidence.",
                response_format="json"
            ))
            analysis_results['category'] = category_request.output_data if category_request.ok else None
        
        # Action item detection
        if 'action_items' in analysis_types:
            action_request = await ai_enhanced_service.process_ai_request(AIRequest(
                request_id=f"actions_{int(datetime.utcnow().timestamp())}",
                task_type=AITaskType.MESSAGE_SUMMARIZATION,
                model_type=model_type_enum,
                service_type=service_type_enum,
                input_data=f"Extract action items from: {content}",
                context={
                    'task': 'action_item_extraction',
                    'platform': platform
                },
                platform=platform,
                system_prompt="You are an expert action item extraction assistant. Extract actionable items."
            ))
            analysis_results['action_items'] = action_request.output_data if action_request.ok else None
        
        return create_ai_response(
            True,
            data={
                'content': content,
                'platform': platform,
                'analysis': analysis_results,
                'analysis_types': analysis_types,
                'model_type': model_type,
                'service_type': service_type,
                'confidence': {
                    'sentiment': analysis_results.get('sentiment', {}).get('confidence', 0.0),
                    'topics': analysis_results.get('topics', {}).get('confidence', 0.0),
                    'category': analysis_results.get('category', {}).get('confidence', 0.0)
                }
            },
            message="Message analyzed successfully with AI"
        )
    
    except Exception as e:
        logger.error(f"AI message analysis error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/summarize_messages', methods=['POST'])
def summarize_messages_ai():
    """Summarize messages with AI"""
    try:
        data = get_ai_request_data()
        messages = data.get('messages', [])
        platform = data.get('platform')
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        summary_type = data.get('summary_type', 'comprehensive')
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        
        if not messages:
            return create_ai_response(False, error="messages is required")
        
        if not ai_enhanced_service:
            return create_ai_response(False, error="AI service not available"), 503
        
        # Validate parameters
        try:
            model_type_enum = validate_ai_model_type(model_type)
            service_type_enum = validate_ai_service_type(service_type)
        except ValueError as e:
            return create_ai_response(False, error=str(e)), 400
        
        # Perform summarization
        summary_request = await ai_enhanced_service.process_ai_request(AIRequest(
            request_id=f"summary_{int(datetime.utcnow().timestamp())}",
            task_type=AITaskType.MESSAGE_SUMMARIZATION,
            model_type=model_type_enum,
            service_type=service_type_enum,
            input_data=messages,
            context={
                'platform': platform,
                'workspace_id': workspace_id,
                'channel_id': channel_id,
                'summary_type': summary_type
            },
            platform=platform,
            user_id=user_id,
            max_tokens=1000,
            temperature=0.3,
            system_prompt="You are an expert message summarization assistant for unified communication platforms."
        ))
        
        if summary_request.ok:
            # Store summary in memory
            if AtomMemoryService:
                memory_data = {
                    'type': 'ai_message_summary',
                    'workspace_id': workspace_id,
                    'channel_id': channel_id,
                    'summary_data': summary_request.output_data,
                    'message_count': len(messages),
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_ai_response(
                True,
                data={
                    'summary': summary_request.output_data,
                    'message_count': len(messages),
                    'workspace_id': workspace_id,
                    'channel_id': channel_id,
                    'platform': platform,
                    'summary_type': summary_type,
                    'model_type': model_type,
                    'service_type': service_type,
                    'confidence': summary_request.confidence,
                    'processing_time': summary_request.processing_time
                },
                message="Messages summarized successfully with AI"
            )
        else:
            return create_ai_response(False, error="Message summarization failed"), 500
    
    except Exception as e:
        logger.error(f"AI message summarization error: {e}")
        return create_ai_response(False, error=str(e)), 500

# AI-Powered Search
@ai_bp.route('/intelligent_search', methods=['POST'])
def intelligent_search_ai():
    """Perform AI-powered intelligent search"""
    try:
        data = get_ai_request_data()
        query = data.get('query')
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        search_type = data.get('search_type', 'semantic')
        limit = data.get('limit', 50)
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        enhance_results = data.get('enhance_results', True)
        
        if not query:
            return create_ai_response(False, error="query is required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Validate parameters
        try:
            model_type_enum = validate_ai_model_type(model_type)
            service_type_enum = validate_ai_service_type(service_type)
        except ValueError as e:
            return create_ai_response(False, error=str(e)), 400
        
        # Perform intelligent search
        search_options = {
            'query': query,
            'workspace_id': workspace_id,
            'channel_id': channel_id,
            'user_id': user_id,
            'search_type': search_type,
            'limit': limit,
            'enhance_results': enhance_results,
            'model_type': model_type,
            'service_type': service_type
        }
        
        search_results = await atom_ai_integration.intelligent_search(
            query=query,
            workspace_id=workspace_id,
            channel_id=channel_id,
            user_id=user_id,
            options=search_options
        )
        
        # Store search in memory
        if AtomMemoryService:
            memory_data = {
                'type': 'ai_intelligent_search',
                'query': query,
                'workspace_id': workspace_id,
                'channel_id': channel_id,
                'result_count': len(search_results),
                'search_type': search_type,
                'user_id': user_id,
                'timestamp': datetime.utcnow().isoformat()
            }
            await AtomMemoryService.store(memory_data)
        
        # Index for search service
        if AtomSearchService:
            for result in search_results:
                search_data = {
                    'type': 'ai_search_result',
                    'id': result.get('id'),
                    'title': result.get('title', result.get('content', '')[:100]),
                    'content': result.get('content', ''),
                    'metadata': {
                        'query': query,
                        'workspace_id': workspace_id,
                        'channel_id': channel_id,
                        'user_id': user_id,
                        'search_type': search_type,
                        'relevance_score': result.get('relevance_score', 0.0),
                        'timestamp': datetime.utcnow().isoformat()
                    }
                }
                await AtomSearchService.index(search_data)
        
        return create_ai_response(
            True,
            data={
                'query': query,
                'results': search_results,
                'total_count': len(search_results),
                'workspace_id': workspace_id,
                'channel_id': channel_id,
                'search_type': search_type,
                'enhance_results': enhance_results,
                'model_type': model_type,
                'service_type': service_type,
                'limit': limit,
                'search_time': datetime.utcnow().isoformat()
            },
            message=f"Intelligent search completed: {len(search_results)} results found"
        )
    
    except Exception as e:
        logger.error(f"AI intelligent search error: {e}")
        return create_ai_response(False, error=str(e)), 500

# AI Conversation Management
@ai_bp.route('/conversation/start', methods=['POST'])
def start_ai_conversation():
    """Start AI-powered conversation"""
    try:
        data = get_ai_request_data()
        user_id = data.get('user_id')
        platform = data.get('platform')
        workspace_id = data.get('workspace_id')
        conversation_type = data.get('conversation_type', 'general')
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        
        if not all([user_id, platform]):
            return create_ai_response(False, error="user_id and platform are required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Start conversation
        conversation_id = await atom_ai_integration.start_ai_conversation(
            user_id=user_id,
            platform=platform,
            workspace_id=workspace_id
        )
        
        if conversation_id:
            return create_ai_response(
                True,
                data={
                    'conversation_id': conversation_id,
                    'user_id': user_id,
                    'platform': platform,
                    'workspace_id': workspace_id,
                    'conversation_type': conversation_type,
                    'model_type': model_type,
                    'service_type': service_type,
                    'created_at': datetime.utcnow().isoformat()
                },
                message="AI conversation started successfully"
            )
        else:
            return create_ai_response(False, error="Failed to start conversation"), 500
    
    except Exception as e:
        logger.error(f"Start AI conversation error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/conversation/continue', methods=['POST'])
def continue_ai_conversation():
    """Continue AI-powered conversation"""
    try:
        data = get_ai_request_data()
        conversation_id = data.get('conversation_id')
        message = data.get('message')
        user_id = data.get('user_id')
        preserve_context = data.get('preserve_context', True)
        
        if not all([conversation_id, message]):
            return create_ai_response(False, error="conversation_id and message are required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Continue conversation
        response = await atom_ai_integration.continue_ai_conversation(
            conversation_id=conversation_id,
            message=message,
            user_id=user_id
        )
        
        if response.get('ok'):
            # Store in memory
            if AtomMemoryService:
                memory_data = {
                    'type': 'ai_conversation',
                    'conversation_id': conversation_id,
                    'user_message': message,
                    'ai_response': response.get('response'),
                    'user_id': user_id,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_ai_response(
                True,
                data={
                    'conversation_id': conversation_id,
                    'user_message': message,
                    'ai_response': response.get('response'),
                    'confidence': response.get('confidence', 0.8),
                    'processing_time': response.get('processing_time', 0.0),
                    'token_usage': response.get('token_usage', {}),
                    'preserve_context': preserve_context
                },
                message="Conversation continued successfully with AI"
            )
        else:
            return create_ai_response(False, error=response.get('error', 'Conversation failed')), 500
    
    except Exception as e:
        logger.error(f"Continue AI conversation error: {e}")
        return create_ai_response(False, error=str(e)), 500

# Natural Language Commands
@ai_bp.route('/commands/process', methods=['POST'])
def process_natural_command():
    """Process natural language command with AI"""
    try:
        data = get_ai_request_data()
        command = data.get('command')
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        platform = data.get('platform')
        execute_action = data.get('execute_action', True)
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        
        if not all([command, user_id]):
            return create_ai_response(False, error="command and user_id are required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Process command
        command_result = await atom_ai_integration.process_natural_language_command(
            command=command,
            user_id=user_id,
            workspace_id=workspace_id,
            platform=platform
        )
        
        if command_result.get('action') and execute_action:
            # Execute the suggested action
            execution_result = await self._execute_ai_command_action(
                command_result,
                user_id,
                workspace_id,
                platform
            )
            command_result['execution_result'] = execution_result
        
        # Store command in memory
        if AtomMemoryService:
            memory_data = {
                'type': 'ai_natural_command',
                'command': command,
                'command_result': command_result,
                'user_id': user_id,
                'workspace_id': workspace_id,
                'platform': platform,
                'timestamp': datetime.utcnow().isoformat()
            }
            await AtomMemoryService.store(memory_data)
        
        return create_ai_response(
            True,
            data={
                'command': command,
                'result': command_result,
                'user_id': user_id,
                'workspace_id': workspace_id,
                'platform': platform,
                'model_type': model_type,
                'service_type': service_type,
                'executed': execute_action
            },
            message="Natural language command processed successfully"
        )
    
    except Exception as e:
        logger.error(f"Process natural command error: {e}")
        return create_ai_response(False, error=str(e)), 500

# AI-Enhanced Content
@ai_bp.route('/content/generate', methods=['POST'])
def generate_ai_content():
    """Generate content with AI"""
    try:
        data = get_ai_request_data()
        content_request = data.get('content_request', {})
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        platform = data.get('platform')
        content_type = content_request.get('type', 'message')
        tone = content_request.get('tone', 'professional')
        context = content_request.get('context', {})
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        
        if not all([content_request, user_id]):
            return create_ai_response(False, error="content_request and user_id are required")
        
        if not ai_enhanced_service:
            return create_ai_response(False, error="AI service not available"), 503
        
        # Validate parameters
        try:
            model_type_enum = validate_ai_model_type(model_type)
            service_type_enum = validate_ai_service_type(service_type)
        except ValueError as e:
            return create_ai_response(False, error=str(e)), 400
        
        # Generate content
        content_request_full = {
            **content_request,
            'type': content_type,
            'tone': tone,
            'context': context,
            'platform': platform
        }
        
        content_result = await ai_enhanced_service.process_ai_request(AIRequest(
            request_id=f"content_{int(datetime.utcnow().timestamp())}",
            task_type=AITaskType.CONTENT_GENERATION,
            model_type=model_type_enum,
            service_type=service_type_enum,
            input_data=content_request_full,
            context={
                'task': 'content_generation',
                'user_id': user_id,
                'workspace_id': workspace_id,
                'platform': platform
            },
            platform=platform,
            user_id=user_id,
            system_prompt="You are an expert content generation assistant for unified communication platforms.",
            temperature=0.7
        ))
        
        if content_result.ok:
            # Store generated content in memory
            if AtomMemoryService:
                memory_data = {
                    'type': 'ai_generated_content',
                    'content_request': content_request_full,
                    'generated_content': content_result.output_data,
                    'user_id': user_id,
                    'workspace_id': workspace_id,
                    'platform': platform,
                    'timestamp': datetime.utcnow().isoformat()
                }
                await AtomMemoryService.store(memory_data)
            
            return create_ai_response(
                True,
                data={
                    'content_request': content_request_full,
                    'generated_content': content_result.output_data,
                    'user_id': user_id,
                    'workspace_id': workspace_id,
                    'platform': platform,
                    'content_type': content_type,
                    'tone': tone,
                    'model_type': model_type,
                    'service_type': service_type,
                    'confidence': content_result.confidence,
                    'processing_time': content_result.processing_time,
                    'token_usage': content_result.token_usage
                },
                message="Content generated successfully with AI"
            )
        else:
            return create_ai_response(False, error="Content generation failed"), 500
    
    except Exception as e:
        logger.error(f"Generate AI content error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/content/enhance', methods=['POST'])
def enhance_content_ai():
    """Enhance existing content with AI"""
    try:
        data = get_ai_request_data()
        content = data.get('content')
        enhancement_type = data.get('enhancement_type', 'improve')
        user_id = data.get('user_id')
        workspace_id = data.get('workspace_id')
        platform = data.get('platform')
        options = data.get('options', {})
        model_type = data.get('model_type', 'gpt-4')
        service_type = data.get('service_type', 'openai')
        
        if not content:
            return create_ai_response(False, error="content is required")
        
        if not ai_enhanced_service:
            return create_ai_response(False, error="AI service not available"), 503
        
        # Validate parameters
        try:
            model_type_enum = validate_ai_model_type(model_type)
            service_type_enum = validate_ai_service_type(service_type)
        except ValueError as e:
            return create_ai_response(False, error=str(e)), 400
        
        # Enhance content
        enhancement_request = {
            'original_content': content,
            'enhancement_type': enhancement_type,
            'options': options,
            'platform': platform,
            'context': options.get('context', {})
        }
        
        enhancement_result = await ai_enhanced_service.process_ai_request(AIRequest(
            request_id=f"enhance_{int(datetime.utcnow().timestamp())}",
            task_type=AITaskType.CONTENT_GENERATION,
            model_type=model_type_enum,
            service_type=service_type_enum,
            input_data=enhancement_request,
            context={
                'task': 'content_enhancement',
                'user_id': user_id,
                'workspace_id': workspace_id,
                'platform': platform
            },
            platform=platform,
            user_id=user_id,
            system_prompt="You are an expert content enhancement assistant for unified communication platforms.",
            temperature=0.5
        ))
        
        if enhancement_result.ok:
            return create_ai_response(
                True,
                data={
                    'original_content': content,
                    'enhanced_content': enhancement_result.output_data,
                    'enhancement_type': enhancement_type,
                    'options': options,
                    'user_id': user_id,
                    'workspace_id': workspace_id,
                    'platform': platform,
                    'model_type': model_type,
                    'service_type': service_type,
                    'confidence': enhancement_result.confidence,
                    'processing_time': enhancement_result.processing_time,
                    'token_usage': enhancement_result.token_usage
                },
                message="Content enhanced successfully with AI"
            )
        else:
            return create_ai_response(False, error="Content enhancement failed"), 500
    
    except Exception as e:
        logger.error(f"Enhance content error: {e}")
        return create_ai_response(False, error=str(e)), 500

# AI-Enhanced Workspaces and Channels
@ai_bp.route('/workspaces/intelligent', methods=['POST'])
def get_intelligent_workspaces():
    """Get AI-enhanced workspaces"""
    try:
        data = get_ai_request_data()
        user_id = data.get('user_id')
        include_insights = data.get('include_insights', True)
        include_predictions = data.get('include_predictions', True)
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Get intelligent workspaces
        workspaces = await atom_ai_integration.get_intelligent_workspaces(user_id)
        
        # Filter based on preferences
        filtered_workspaces = workspaces
        if not include_insights:
            for workspace in filtered_workspaces:
                workspace.pop('ai_insights', None)
        
        if not include_predictions:
            for workspace in filtered_workspaces:
                workspace['ai_insights'].pop('predicted_activity', None)
        
        return create_ai_response(
            True,
            data={
                'workspaces': filtered_workspaces,
                'total_count': len(filtered_workspaces),
                'user_id': user_id,
                'include_insights': include_insights,
                'include_predictions': include_predictions
            },
            message=f"Retrieved {len(filtered_workspaces)} intelligent workspaces"
        )
    
    except Exception as e:
        logger.error(f"Get intelligent workspaces error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/channels/intelligent', methods=['POST'])
def get_intelligent_channels():
    """Get AI-enhanced channels"""
    try:
        data = get_ai_request_data()
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        include_insights = data.get('include_insights', True)
        include_predictions = data.get('include_predictions', True)
        channel_types = data.get('channel_types', [])
        
        if not workspace_id:
            return create_ai_response(False, error="workspace_id is required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Get intelligent channels
        channels = await atom_ai_integration.get_intelligent_channels(workspace_id, user_id)
        
        # Filter based on preferences
        filtered_channels = channels
        
        # Filter by channel types
        if channel_types:
            filtered_channels = [
                channel for channel in filtered_channels
                if channel['type'] in channel_types
            ]
        
        # Filter insights and predictions
        if not include_insights:
            for channel in filtered_channels:
                channel.pop('ai_insights', None)
        
        if not include_predictions:
            for channel in filtered_channels:
                channel['ai_insights'].pop('predicted_messages', None)
        
        return create_ai_response(
            True,
            data={
                'channels': filtered_channels,
                'total_count': len(filtered_channels),
                'workspace_id': workspace_id,
                'user_id': user_id,
                'channel_types': channel_types,
                'include_insights': include_insights,
                'include_predictions': include_predictions
            },
            message=f"Retrieved {len(filtered_channels)} intelligent channels"
        )
    
    except Exception as e:
        logger.error(f"Get intelligent channels error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/messages/intelligent', methods=['POST'])
def get_intelligent_messages():
    """Get AI-enhanced messages"""
    try:
        data = get_ai_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        user_id = data.get('user_id')
        limit = data.get('limit', 100)
        include_analysis = data.get('include_analysis', True)
        analysis_types = data.get('analysis_types', ['sentiment', 'topics'])
        before = data.get('before')
        after = data.get('after')
        
        if not all([workspace_id, channel_id]):
            return create_ai_response(False, error="workspace_id and channel_id are required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Get intelligent messages
        options = {
            'limit': limit,
            'include_analysis': include_analysis,
            'analysis_types': analysis_types,
            'before': before,
            'after': after,
            'user_id': user_id
        }
        
        messages = await atom_ai_integration.get_intelligent_messages(
            workspace_id, channel_id, limit, user_id, options
        )
        
        return create_ai_response(
            True,
            data={
                'messages': messages,
                'total_count': len(messages),
                'workspace_id': workspace_id,
                'channel_id': channel_id,
                'limit': limit,
                'include_analysis': include_analysis,
                'analysis_types': analysis_types
            },
            message=f"Retrieved {len(messages)} intelligent messages"
        )
    
    except Exception as e:
        logger.error(f"Get intelligent messages error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/messages/intelligent_send', methods=['POST'])
def send_intelligent_message():
    """Send AI-enhanced message"""
    try:
        data = get_ai_request_data()
        workspace_id = data.get('workspace_id')
        channel_id = data.get('channel_id')
        content = data.get('content')
        user_id = data.get('user_id')
        enhance_content = data.get('enhance_content', True)
        analyze_after_send = data.get('analyze_after_send', True)
        content_options = data.get('content_options', {})
        
        if not all([workspace_id, channel_id, content]):
            return create_ai_response(False, error="workspace_id, channel_id, and content are required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Send intelligent message
        options = {
            'enhance_content': enhance_content,
            'analyze_after_send': analyze_after_send,
            'content_options': content_options,
            'user_id': user_id
        }
        
        result = await atom_ai_integration.send_intelligent_message(
            workspace_id, channel_id, content, options
        )
        
        if result.get('ok'):
            return create_ai_response(
                True,
                data=result,
                message="Intelligent message sent successfully"
            )
        else:
            return create_ai_response(False, error=result.get('error')), 400
    
    except Exception as e:
        logger.error(f"Send intelligent message error: {e}")
        return create_ai_response(False, error=str(e)), 500

# AI Analytics
@ai_bp.route('/analytics/intelligent', methods=['POST'])
def get_intelligent_analytics():
    """Get AI-enhanced analytics"""
    try:
        data = get_ai_request_data()
        metric = data.get('metric')
        time_range = data.get('time_range', 'last_7_days')
        workspace_id = data.get('workspace_id')
        user_id = data.get('user_id')
        options = data.get('options', {})
        enhance_analytics = data.get('enhance_analytics', True)
        
        if not metric:
            return create_ai_response(False, error="metric is required")
        
        if not atom_ai_integration:
            return create_ai_response(False, error="AI integration not available"), 503
        
        # Get intelligent analytics
        analytics_result = await atom_ai_integration.get_intelligent_analytics(
            metric, time_range, workspace_id, options
        )
        
        return create_ai_response(
            True,
            data={
                'metric': metric,
                'time_range': time_range,
                'analytics': analytics_result,
                'workspace_id': workspace_id,
                'user_id': user_id,
                'enhance_analytics': enhance_analytics,
                'options': options
            },
            message="Intelligent analytics retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get intelligent analytics error: {e}")
        return create_ai_response(False, error=str(e)), 500

@ai_bp.route('/analytics/performance', methods=['POST'])
def get_ai_performance_metrics():
    """Get AI service performance metrics"""
    try:
        data = get_ai_request_data()
        include_detailed = data.get('include_detailed', False)
        time_range = data.get('time_range', 'last_24_hours')
        
        if not ai_enhanced_service:
            return create_ai_response(False, error="AI service not available"), 503
        
        # Get performance metrics
        performance_metrics = await ai_enhanced_service.get_performance_metrics()
        
        return create_ai_response(
            True,
            data={
                'performance_metrics': performance_metrics,
                'include_detailed': include_detailed,
                'time_range': time_range,
                'timestamp': datetime.utcnow().isoformat()
            },
            message="AI performance metrics retrieved successfully"
        )
    
    except Exception as e:
        logger.error(f"Get AI performance metrics error: {e}")
        return create_ai_response(False, error=str(e)), 500

# Error handlers
@ai_bp.errorhandler(404)
def ai_not_found(error):
    return create_ai_response(False, error="Endpoint not found"), 404

@ai_bp.errorhandler(500)
def ai_internal_error(error):
    logger.error(f"AI internal server error: {error}")
    return create_ai_response(False, error="Internal server error"), 500

# Register blueprint
def register_ai_api(app):
    """Register AI API blueprint"""
    app.register_blueprint(ai_bp)
    logger.info("AI Enhanced API blueprint registered")

# Service initialization
def initialize_ai_services():
    """Initialize AI services"""
    try:
        # Validate configuration
        if not validate_ai_config():
            return False
        
        # Initialize services
        if ai_enhanced_service:
            logger.info("AI Enhanced service initialized")
        
        if atom_ai_integration:
            logger.info("AI integration service initialized")
        
        return True
    
    except Exception as e:
        logger.error(f"Error initializing AI services: {e}")
        return False

# Export for external use
__all__ = [
    'ai_bp',
    'register_ai_api',
    'initialize_ai_services',
    'create_ai_response',
    'get_ai_request_data'
]