"""
🤖 Zoom AI Analytics API Routes
Comprehensive AI analytics, speech-to-text, and predictive analytics endpoints
"""

import os
import json
import logging
import asyncio
import base64
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from flask import Blueprint, request, jsonify, abort

from zoom_ai_analytics_engine import ZoomAIAnalyticsEngine
from zoom_advanced_analytics import ZoomAdvancedAnalytics
from zoom_speech_to_text import ZoomSpeechToText, TranscriptionProvider, AudioFormat
from zoom_predictive_analytics import ZoomPredictiveAnalytics, PredictionType, ModelType

logger = logging.getLogger(__name__)

# Create blueprint
zoom_ai_analytics_bp = Blueprint("zoom_ai_analytics", __name__)

# Global analytics services
ai_analytics_engine: Optional[ZoomAIAnalyticsEngine] = None
advanced_analytics: Optional[ZoomAdvancedAnalytics] = None
speech_to_text: Optional[ZoomSpeechToText] = None
predictive_analytics: Optional[ZoomPredictiveAnalytics] = None

def init_zoom_ai_analytics_services(db_pool: asyncpg.Pool, 
                                  openai_api_key: Optional[str] = None,
                                  google_credentials: Optional[str] = None,
                                  azure_credentials: Optional[str] = None):
    """Initialize all Zoom AI analytics services"""
    global ai_analytics_engine, advanced_analytics, speech_to_text, predictive_analytics
    
    try:
        # Initialize AI analytics engine
        ai_analytics_engine = ZoomAIAnalyticsEngine(db_pool, openai_api_key)
        advanced_analytics = ZoomAdvancedAnalytics(db_pool, ai_analytics_engine)
        speech_to_text = ZoomSpeechToText(db_pool, openai_api_key, google_credentials, azure_credentials)
        predictive_analytics = ZoomPredictiveAnalytics(db_pool)
        
        # Start processing
        await ai_analytics_engine.start_processing()
        await speech_to_text.start_processing()
        await predictive_analytics.start_processing()
        
        logger.info("All Zoom AI analytics services initialized successfully")
        return {
            'ai_analytics_engine': ai_analytics_engine,
            'advanced_analytics': advanced_analytics,
            'speech_to_text': speech_to_text,
            'predictive_analytics': predictive_analytics
        }
        
    except Exception as e:
        logger.error(f"Failed to initialize Zoom AI analytics services: {e}")
        raise

def format_response(data: Any, endpoint: str, status: str = 'success') -> Dict[str, Any]:
    """Format API response"""
    return {
        'ok': status == 'success',
        'data': data,
        'endpoint': endpoint,
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_ai_analytics_api'
    }

def format_error_response(error: str, endpoint: str, status_code: int = 500) -> tuple:
    """Format error response"""
    error_response = {
        'ok': False,
        'error': {
            'code': 'AI_ANALYTICS_ERROR',
            'message': error,
            'endpoint': endpoint
        },
        'timestamp': datetime.now(timezone.utc).isoformat(),
        'source': 'zoom_ai_analytics_api'
    }
    return jsonify(error_response), status_code

def validate_required_fields(data: Dict[str, Any], required_fields: list) -> tuple:
    """Validate required fields in request data"""
    missing_fields = [field for field in required_fields if field not in data or not data[field]]
    
    if missing_fields:
        error_msg = f"Missing required fields: {', '.join(missing_fields)}"
        return False, error_msg
    
    return True, None

def get_client_info() -> Dict[str, str]:
    """Get client information for security"""
    return {
        'user_agent': request.headers.get('User-Agent', 'Unknown'),
        'ip_address': request.environ.get('REMOTE_ADDR', request.headers.get('X-Forwarded-For', 'Unknown')),
        'referer': request.headers.get('Referer', 'Unknown'),
        'origin': request.headers.get('Origin', 'Unknown'),
        'accept_language': request.headers.get('Accept-Language', 'Unknown')
    }

# === AI INSIGHTS ENDPOINTS ===

@zoom_ai_analytics_bp.route("/api/zoom/ai/insights/summary", methods=["POST"])
async def generate_ai_summary():
    """Generate AI-powered meeting summary"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id'])
        if not is_valid:
            return format_error_response(error, '/ai/insights/summary', 400)
        
        meeting_id = request_data['meeting_id']
        summary_type = request_data.get('summary_type', 'comprehensive')
        include_sentiment = request_data.get('include_sentiment', True)
        include_action_items = request_data.get('include_action_items', True)
        include_key_decisions = request_data.get('include_key_decisions', True)
        
        # Generate summary
        if ai_analytics_engine:
            insight = await ai_analytics_engine.generate_meeting_summary(meeting_id, summary_type)
            
            if insight:
                response_data = {
                    'insight_id': insight.insight_id,
                    'meeting_id': meeting_id,
                    'summary_type': summary_type,
                    'title': insight.title,
                    'description': insight.description,
                    'confidence': insight.confidence,
                    'data': insight.data,
                    'include_sentiment': include_sentiment,
                    'include_action_items': include_action_items,
                    'include_key_decisions': include_key_decisions,
                    'created_at': insight.created_at.isoformat(),
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/insights/summary')
            else:
                return format_error_response('Failed to generate AI summary', '/ai/insights/summary', 500)
        else:
            return format_error_response('AI analytics engine not available', '/ai/insights/summary', 503)
        
    except Exception as e:
        logger.error(f"Failed to generate AI summary: {e}")
        return format_error_response(str(e), '/ai/insights/summary', 500)

@zoom_ai_analytics_bp.route("/api/zoom/ai/insights/participant", methods=["POST"])
async def generate_participant_insights():
    """Generate AI-powered participant insights"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['meeting_id', 'participant_id']
        )
        if not is_valid:
            return format_error_response(error, '/ai/insights/participant', 400)
        
        meeting_id = request_data['meeting_id']
        participant_id = request_data['participant_id']
        insight_types = request_data.get('insight_types', [
            'engagement', 'sentiment', 'behavior', 'collaboration'
        ])
        include_recommendations = request_data.get('include_recommendations', True)
        
        # Analyze participant
        if ai_analytics_engine:
            behavior = await ai_analytics_engine.analyze_participant_engagement(
                meeting_id, participant_id
            )
            
            if behavior:
                # Generate insights based on behavior
                insights = await _generate_participant_insights(
                    behavior, insight_types, include_recommendations
                )
                
                response_data = {
                    'participant_id': participant_id,
                    'meeting_id': meeting_id,
                    'insight_types': insight_types,
                    'behavior': {
                        'speaking_time_seconds': behavior.speaking_time_seconds,
                        'speaking_turns': behavior.speaking_turns,
                        'average_utterance_length': behavior.average_utterance_length,
                        'sentiment_score': behavior.sentiment_score,
                        'engagement_score': behavior.engagement_score,
                        'dominance_score': behavior.dominance_score,
                        'collaboration_score': behavior.collaboration_score,
                        'interruptions': behavior.interruptions,
                        'interruptions_received': behavior.interruptions_received,
                        'questions_asked': behavior.questions_asked,
                        'responses_provided': behavior.responses_provided,
                        'speaking_rate': behavior.speaking_rate,
                        'vocal_features': behavior.vocal_features
                    },
                    'insights': insights,
                    'include_recommendations': include_recommendations,
                    'created_at': behavior.created_at.isoformat(),
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/insights/participant')
            else:
                return format_error_response('Failed to analyze participant', '/ai/insights/participant', 500)
        else:
            return format_error_response('AI analytics engine not available', '/ai/insights/participant', 503)
        
    except Exception as e:
        logger.error(f"Failed to generate participant insights: {e}")
        return format_error_response(str(e), '/ai/insights/participant', 500)

# === SPEECH-TO-TEXT ENDPOINTS ===

@zoom_ai_analytics_bp.route("/api/zoom/ai/speech/transcribe", methods=["POST"])
async def transcribe_speech():
    """Transcribe speech using AI"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['meeting_id', 'participant_id', 'audio_data']
        )
        if not is_valid:
            return format_error_response(error, '/ai/speech/transcribe', 400)
        
        meeting_id = request_data['meeting_id']
        participant_id = request_data['participant_id']
        audio_data = request_data['audio_data']
        audio_format = AudioFormat(request_data.get('audio_format', 'wav'))
        provider = TranscriptionProvider(request_data.get('provider', 'whisper'))
        language = request_data.get('language', 'en')
        
        # Decode audio data if base64 encoded
        if isinstance(audio_data, str):
            audio_data = base64.b64decode(audio_data)
        
        # Transcribe audio
        if speech_to_text:
            transcription_result = await speech_to_text.transcribe_with_provider(
                audio_data, provider, language
            )
            
            if 'error' not in transcription_result:
                response_data = {
                    'success': True,
                    'meeting_id': meeting_id,
                    'participant_id': participant_id,
                    'transcription': transcription_result['text'],
                    'segments': transcription_result.get('segments', []),
                    'confidence': transcription_result.get('confidence', 0),
                    'language': transcription_result.get('language', 'en'),
                    'provider': transcription_result.get('provider', 'whisper'),
                    'model_used': transcription_result.get('model_used', 'unknown'),
                    'processing_time': transcription_result.get('processing_time', 0),
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/speech/transcribe')
            else:
                return format_error_response(
                    transcription_result['error'], 
                    '/ai/speech/transcribe', 
                    500
                )
        else:
            return format_error_response('Speech-to-text service not available', '/ai/speech/transcribe', 503)
        
    except Exception as e:
        logger.error(f"Failed to transcribe speech: {e}")
        return format_error_response(str(e), '/ai/speech/transcribe', 500)

@zoom_ai_analytics_bp.route("/api/zoom/ai/speech/transcribe-file", methods=["POST"])
async def transcribe_file():
    """Transcribe audio file using AI"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['meeting_id', 'participant_id', 'file_path']
        )
        if not is_valid:
            return format_error_response(error, '/ai/speech/transcribe-file', 400)
        
        meeting_id = request_data['meeting_id']
        participant_id = request_data['participant_id']
        file_path = request_data['file_path']
        audio_format = AudioFormat(request_data.get('audio_format', 'wav'))
        provider = TranscriptionProvider(request_data.get('provider', 'whisper'))
        language = request_data.get('language', 'en')
        
        # Transcribe file
        if speech_to_text:
            job_id = await speech_to_text.transcribe_audio_file(
                meeting_id, participant_id, file_path, audio_format, provider, language
            )
            
            if job_id:
                response_data = {
                    'success': True,
                    'job_id': job_id,
                    'meeting_id': meeting_id,
                    'participant_id': participant_id,
                    'file_path': file_path,
                    'audio_format': audio_format.value,
                    'provider': provider.value,
                    'language': language,
                    'status': 'processing',
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/speech/transcribe-file')
            else:
                return format_error_response('Failed to start file transcription', '/ai/speech/transcribe-file', 500)
        else:
            return format_error_response('Speech-to-text service not available', '/ai/speech/transcribe-file', 503)
        
    except Exception as e:
        logger.error(f"Failed to transcribe file: {e}")
        return format_error_response(str(e), '/ai/speech/transcribe-file', 500)

@zoom_ai_analytics_bp.route("/api/zoom/ai/speech/transcription-status", methods=["GET"])
async def get_transcription_status():
    """Get transcription job status"""
    try:
        job_id = request.args.get('job_id')
        
        if not job_id:
            return format_error_response('Missing job_id parameter', '/ai/speech/transcription-status', 400)
        
        # Get job status
        if speech_to_text:
            job = speech_to_text.get_transcription_job(job_id)
            
            if job:
                response_data = {
                    'job_id': job.job_id,
                    'meeting_id': job.meeting_id,
                    'participant_id': job.participant_id,
                    'provider': job.provider.value,
                    'language': job.language,
                    'status': job.status,
                    'progress': job.progress,
                    'started_at': job.started_at.isoformat(),
                    'completed_at': job.completed_at.isoformat() if job.completed_at else None,
                    'error_message': job.error_message,
                    'transcription_segments': job.transcription_segments,
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/speech/transcription-status')
            else:
                return format_error_response('Transcription job not found', '/ai/speech/transcription-status', 404)
        else:
            return format_error_response('Speech-to-text service not available', '/ai/speech/transcription-status', 503)
        
    except Exception as e:
        logger.error(f"Failed to get transcription status: {e}")
        return format_error_response(str(e), '/ai/speech/transcription-status', 500)

# === PREDICTIVE ANALYTICS ENDPOINTS ===

@zoom_ai_analytics_bp.route("/api/zoom/ai/predict/train-model", methods=["POST"])
async def train_predictive_model():
    """Train predictive model"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['prediction_type', 'training_data']
        )
        if not is_valid:
            return format_error_response(error, '/ai/predict/train-model', 400)
        
        prediction_type = PredictionType(request_data['prediction_type'])
        training_data = request_data['training_data']
        model_type = ModelType(request_data.get('model_type', 'random_forest'))
        hyperparameters = request_data.get('hyperparameters', {})
        
        # Train model
        if predictive_analytics:
            model = await predictive_analytics.train_model(
                prediction_type, training_data, model_type, hyperparameters
            )
            
            if model:
                response_data = {
                    'model_id': model.model_id,
                    'prediction_type': model.prediction_type.value,
                    'model_type': model.model_type.value,
                    'training_data_size': model.training_data_size,
                    'validation_data_size': model.validation_data_size,
                    'training_score': model.training_score,
                    'validation_score': model.validation_score,
                    'test_score': model.test_score,
                    'feature_importance': model.feature_importance,
                    'accuracy_metrics': model.accuracy_metrics,
                    'model_version': model.model_version,
                    'is_active': model.is_active,
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/predict/train-model')
            else:
                return format_error_response('Failed to train model', '/ai/predict/train-model', 500)
        else:
            return format_error_response('Predictive analytics service not available', '/ai/predict/train-model', 503)
        
    except Exception as e:
        logger.error(f"Failed to train predictive model: {e}")
        return format_error_response(str(e), '/ai/predict/train-model', 500)

@zoom_ai_analytics_bp.route("/api/zoom/ai/predict/make-prediction", methods=["POST"])
async def make_prediction():
    """Make prediction using trained model"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['prediction_type', 'input_data']
        )
        if not is_valid:
            return format_error_response(error, '/ai/predict/make-prediction', 400)
        
        prediction_type = PredictionType(request_data['prediction_type'])
        input_data = request_data['input_data']
        model_id = request_data.get('model_id')
        horizon = request_data.get('horizon', 'short_term')
        
        # Make prediction
        if predictive_analytics:
            prediction = await predictive_analytics.predict(
                prediction_type, input_data, model_id, horizon
            )
            
            if prediction:
                response_data = {
                    'prediction_id': prediction.prediction_id,
                    'model_id': prediction.model_id,
                    'prediction_type': prediction.prediction_type.value,
                    'prediction_value': prediction.prediction_value,
                    'confidence_score': prediction.confidence_score,
                    'prediction_horizon': prediction.prediction_horizon.value,
                    'input_features': prediction.input_features,
                    'explanation': prediction.explanation,
                    'is_valid': prediction.is_valid,
                    'timestamp': prediction.timestamp.isoformat(),
                    'expires_at': prediction.expires_at.isoformat(),
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/predict/make-prediction')
            else:
                return format_error_response('Failed to make prediction', '/ai/predict/make-prediction', 500)
        else:
            return format_error_response('Predictive analytics service not available', '/ai/predict/make-prediction', 503)
        
    except Exception as e:
        logger.error(f"Failed to make prediction: {e}")
        return format_error_response(str(e), '/ai/predict/make-prediction', 500)

@zoom_ai_analytics_bp.route("/api/zoom/ai/predict/generate-forecast", methods=["POST"])
async def generate_forecast():
    """Generate time series forecast"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(
            request_data, 
            ['prediction_type', 'forecast_period']
        )
        if not is_valid:
            return format_error_response(error, '/ai/predict/generate-forecast', 400)
        
        prediction_type = PredictionType(request_data['prediction_type'])
        forecast_period = (
            datetime.fromisoformat(request_data['forecast_period']['start']),
            datetime.fromisoformat(request_data['forecast_period']['end'])
        )
        historical_data = request_data.get('historical_data')
        model_id = request_data.get('model_id')
        
        # Generate forecast
        if predictive_analytics:
            forecast = await predictive_analytics.generate_forecast(
                prediction_type, forecast_period, historical_data, model_id
            )
            
            if forecast:
                response_data = {
                    'forecast_id': forecast.forecast_id,
                    'prediction_type': forecast.prediction_type.value,
                    'forecast_period': {
                        'start': forecast.forecast_period[0].isoformat(),
                        'end': forecast.forecast_period[1].isoformat()
                    },
                    'forecast_values': forecast.forecast_values,
                    'confidence_intervals': forecast.confidence_intervals,
                    'trend_direction': forecast.trend_direction,
                    'seasonality_detected': forecast.seasonality_detected,
                    'forecast_accuracy': forecast.forecast_accuracy,
                    'model_id': forecast.model_id,
                    'timestamp': forecast.timestamp.isoformat(),
                    'client_info': get_client_info()
                }
                
                return format_response(response_data, '/ai/predict/generate-forecast')
            else:
                return format_error_response('Failed to generate forecast', '/ai/predict/generate-forecast', 500)
        else:
            return format_error_response('Predictive analytics service not available', '/ai/predict/generate-forecast', 503)
        
    except Exception as e:
        logger.error(f"Failed to generate forecast: {e}")
        return format_error_response(str(e), '/ai/predict/generate-forecast', 500)

# === COMPREHENSIVE ANALYTICS ENDPOINTS ===

@zoom_ai_analytics_bp.route("/api/zoom/ai/analytics/comprehensive", methods=["POST"])
async def comprehensive_analytics():
    """Generate comprehensive AI analytics"""
    try:
        request_data = request.get_json()
        
        # Validate required fields
        is_valid, error = validate_required_fields(request_data, ['meeting_id'])
        if not is_valid:
            return format_error_response(error, '/ai/analytics/comprehensive', 400)
        
        meeting_id = request_data['meeting_id']
        analysis_types = request_data.get('analysis_types', [
            'participation', 'engagement', 'sentiment', 'collaboration', 
            'productivity', 'business_impact'
        ])
        include_insights = request_data.get('include_insights', True)
        include_predictions = request_data.get('include_predictions', True)
        include_transcriptions = request_data.get('include_transcriptions', True)
        
        # Generate comprehensive analytics
        analytics_results = {}
        
        # Advanced analytics
        if advanced_analytics:
            analytics_results['advanced_analytics'] = await advanced_analytics.calculate_meeting_analytics(meeting_id)
        
        # Participant behaviors
        if ai_analytics_engine:
            participants = await _get_meeting_participants(meeting_id)
            analytics_results['participant_behaviors'] = {}
            
            for participant_id in participants:
                behavior = await ai_analytics_engine.analyze_participant_engagement(meeting_id, participant_id)
                if behavior:
                    analytics_results['participant_behaviors'][participant_id] = {
                        'speaking_time_seconds': behavior.speaking_time_seconds,
                        'engagement_score': behavior.engagement_score,
                        'sentiment_score': behavior.sentiment_score,
                        'collaboration_score': behavior.collaboration_score
                    }
        
        # Transcriptions
        if include_transcriptions and speech_to_text:
            analytics_results['transcriptions'] = [
                {
                    'segment_id': seg.segment_id,
                    'participant_id': seg.participant_id,
                    'text': seg.text,
                    'confidence': seg.confidence,
                    'start_time': seg.start_time,
                    'end_time': seg.end_time
                }
                for seg in speech_to_text.get_transcription_segments(meeting_id)
            ]
        
        # Predictions
        if include_predictions and predictive_analytics:
            analytics_results['predictions'] = {}
            
            for prediction_type in ['meeting_attendance', 'participant_engagement', 'satisfaction_score']:
                input_data = {'meeting_id': meeting_id}
                prediction = await predictive_analytics.predict(
                    PredictionType(prediction_type), input_data
                )
                if prediction:
                    analytics_results['predictions'][prediction_type] = {
                        'prediction_value': prediction.prediction_value,
                        'confidence_score': prediction.confidence_score,
                        'explanation': prediction.explanation
                    }
        
        # AI insights
        if include_insights and ai_analytics_engine:
            analytics_results['ai_insights'] = ai_analytics_engine.get_meeting_insights(meeting_id)
        
        response_data = {
            'meeting_id': meeting_id,
            'analysis_types': analysis_types,
            'analytics': analytics_results,
            'include_insights': include_insights,
            'include_predictions': include_predictions,
            'include_transcriptions': include_transcriptions,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            'client_info': get_client_info()
        }
        
        return format_response(response_data, '/ai/analytics/comprehensive')
        
    except Exception as e:
        logger.error(f"Failed to generate comprehensive analytics: {e}")
        return format_error_response(str(e), '/ai/analytics/comprehensive', 500)

# === AI PERFORMANCE MONITORING ENDPOINTS ===

@zoom_ai_analytics_bp.route("/api/zoom/ai/performance/metrics", methods=["GET"])
async def get_ai_performance_metrics():
    """Get AI service performance metrics"""
    try:
        metrics_data = {}
        
        # AI analytics engine metrics
        if ai_analytics_engine:
            metrics_data['ai_analytics_engine'] = ai_analytics_engine.get_metrics()
        
        # Speech-to-text metrics
        if speech_to_text:
            metrics_data['speech_to_text'] = speech_to_text.get_metrics()
        
        # Predictive analytics metrics
        if predictive_analytics:
            metrics_data['predictive_analytics'] = predictive_analytics.get_metrics()
        
        # Advanced analytics metrics
        if advanced_analytics:
            metrics_data['advanced_analytics'] = advanced_analytics.get_performance_metrics()
        
        # Calculate combined metrics
        combined_metrics = {
            'total_ai_requests': sum(
                metrics.get('insights_generated', 0) + 
                metrics.get('audio_segments_processed', 0) +
                metrics.get('predictions_generated', 0)
                for metrics in metrics_data.values()
            ),
            'total_processing_time': sum(
                metrics.get('average_processing_time', 0) 
                for metrics in metrics_data.values()
            ) / len(metrics_data) if metrics_data else 0,
            'service_health': {
                service: 'healthy' if getattr(service, 'is_running', False) else 'unhealthy'
                for service_name, service in [
                    ('ai_analytics_engine', ai_analytics_engine),
                    ('speech_to_text', speech_to_text),
                    ('predictive_analytics', predictive_analytics)
                ]
            }
        }
        
        metrics_data['combined'] = combined_metrics
        
        response_data = {
            'metrics': metrics_data,
            'timestamp': datetime.now(timezone.utc).isoformat(),
            'client_info': get_client_info()
        }
        
        return format_response(response_data, '/ai/performance/metrics')
        
    except Exception as e:
        logger.error(f"Failed to get AI performance metrics: {e}")
        return format_error_response(str(e), '/ai/performance/metrics', 500)

@zoom_ai_analytics_bp.route("/api/zoom/ai/health", methods=["GET"])
async def ai_health_check():
    """Health check for all AI services"""
    try:
        health_status = {
            'ai_analytics_engine': {
                'initialized': ai_analytics_engine is not None,
                'running': ai_analytics_engine.is_running if ai_analytics_engine else False
            },
            'advanced_analytics': {
                'initialized': advanced_analytics is not None
            },
            'speech_to_text': {
                'initialized': speech_to_text is not None,
                'running': speech_to_text.is_running if speech_to_text else False
            },
            'predictive_analytics': {
                'initialized': predictive_analytics is not None,
                'running': predictive_analytics.is_running if predictive_analytics else False
            },
            'overall_status': 'healthy'
        }
        
        # Determine overall health
        unhealthy_services = [
            service for service, status in health_status.items()
            if service != 'overall_status' and (
                not status.get('initialized', False) or 
                (status.get('running') is False and status.get('running') is not None)
            )
        ]
        
        if unhealthy_services:
            health_status['overall_status'] = 'degraded' if len(unhealthy_services) < 2 else 'unhealthy'
            health_status['unhealthy_services'] = unhealthy_services
        
        # Get performance snapshot
        performance_snapshot = {}
        if ai_analytics_engine:
            performance_snapshot['ai_analytics_engine'] = ai_analytics_engine.get_metrics()
        if speech_to_text:
            performance_snapshot['speech_to_text'] = speech_to_text.get_metrics()
        if predictive_analytics:
            performance_snapshot['predictive_analytics'] = predictive_analytics.get_metrics()
        
        health_status['performance_snapshot'] = performance_snapshot
        
        if health_status['overall_status'] == 'healthy':
            return format_response(health_status, '/ai/health')
        else:
            return format_error_response(
                f"AI services unhealthy: {', '.join(unhealthy_services)}", 
                '/ai/health', 
                503
            )
        
    except Exception as e:
        logger.error(f"AI health check failed: {e}")
        return format_error_response(f'Health check failed: {e}', '/ai/health', 500)

# === HELPER FUNCTIONS ===

async def _generate_participant_insights(behavior, insight_types, include_recommendations):
    """Generate insights from participant behavior"""
    insights = []
    
    for insight_type in insight_types:
        if insight_type == 'engagement':
            if behavior.engagement_score > 0.8:
                insights.append({
                    'type': 'engagement',
                    'level': 'high',
                    'message': 'Participant shows high engagement',
                    'score': behavior.engagement_score
                })
            elif behavior.engagement_score < 0.3:
                insights.append({
                    'type': 'engagement',
                    'level': 'low',
                    'message': 'Participant shows low engagement',
                    'score': behavior.engagement_score
                })
        
        elif insight_type == 'sentiment':
            if behavior.sentiment_score > 0.5:
                insights.append({
                    'type': 'sentiment',
                    'level': 'positive',
                    'message': 'Participant shows positive sentiment',
                    'score': behavior.sentiment_score
                })
            elif behavior.sentiment_score < -0.5:
                insights.append({
                    'type': 'sentiment',
                    'level': 'negative',
                    'message': 'Participant shows negative sentiment',
                    'score': behavior.sentiment_score
                })
        
        elif insight_type == 'collaboration':
            if behavior.collaboration_score > 0.7:
                insights.append({
                    'type': 'collaboration',
                    'level': 'high',
                    'message': 'Participant shows strong collaboration',
                    'score': behavior.collaboration_score
                })
        
        elif insight_type == 'dominance':
            if behavior.dominance_score > 0.8:
                insights.append({
                    'type': 'dominance',
                    'level': 'high',
                    'message': 'Participant shows high dominance in conversation',
                    'score': behavior.dominance_score
                })
    
    # Add recommendations if requested
    if include_recommendations:
        recommendations = []
        
        if behavior.engagement_score < 0.4:
            recommendations.append("Consider engaging participant more directly")
        
        if behavior.sentiment_score < -0.3:
            recommendations.append("Check if participant has concerns or issues")
        
        if behavior.dominance_score > 0.8 and behavior.collaboration_score < 0.5:
            recommendations.append("Encourage more balanced participation")
        
        insights.append({
            'type': 'recommendations',
            'recommendations': recommendations
        })
    
    return insights

async def _get_meeting_participants(meeting_id):
    """Get participants for a meeting"""
    # This would query the database for meeting participants
    # For now, return placeholder data
    return ['participant_1', 'participant_2', 'participant_3']

# === ERROR HANDLING ===

@zoom_ai_analytics_bp.errorhandler(400)
def bad_request(error):
    """Handle 400 Bad Request"""
    return format_error_response('Bad Request', 'global', 400)

@zoom_ai_analytics_bp.errorhandler(401)
def unauthorized(error):
    """Handle 401 Unauthorized"""
    return format_error_response('Unauthorized', 'global', 401)

@zoom_ai_analytics_bp.errorhandler(403)
def forbidden(error):
    """Handle 403 Forbidden"""
    return format_error_response('Forbidden', 'global', 403)

@zoom_ai_analytics_bp.errorhandler(404)
def not_found(error):
    """Handle 404 Not Found"""
    return format_error_response('Not Found', 'global', 404)

@zoom_ai_analytics_bp.errorhandler(413)
def payload_too_large(error):
    """Handle 413 Payload Too Large"""
    return format_error_response('Audio file too large', 'global', 413)

@zoom_ai_analytics_bp.errorhandler(415)
def unsupported_media_type(error):
    """Handle 415 Unsupported Media Type"""
    return format_error_response('Unsupported audio format', 'global', 415)

@zoom_ai_analytics_bp.errorhandler(429)
def rate_limited(error):
    """Handle 429 Too Many Requests"""
    return format_error_response('Rate Limit Exceeded', 'global', 429)

@zoom_ai_analytics_bp.errorhandler(500)
def internal_error(error):
    """Handle 500 Internal Server Error"""
    logger.error(f"Internal server error: {error}")
    return format_error_response('Internal Server Error', 'global', 500)

@zoom_ai_analytics_bp.errorhandler(503)
def service_unavailable(error):
    """Handle 503 Service Unavailable"""
    return format_error_response('AI Service Unavailable', 'global', 503)