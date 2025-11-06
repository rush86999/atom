"""
🧠 Zoom AI Analytics Engine
Advanced AI-powered analytics and insights for Zoom meetings
"""

import os
import json
import logging
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
from collections import defaultdict, deque

import asyncpg
import httpx
from openai import AsyncOpenAI
import whisper
import torch
import librosa
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.cluster import KMeans
from sklearn.metrics.pairwise import cosine_similarity
from sentence_transformers import SentenceTransformer
import networkx as nx

logger = logging.getLogger(__name__)

class InsightType(Enum):
    """AI insight types"""
    MEETING_SUMMARY = "meeting_summary"
    ACTION_ITEMS = "action_items"
    KEY_DECISIONS = "key_decisions"
    PARTICIPANT_INSIGHTS = "participant_insights"
    SENTIMENT_ANALYSIS = "sentiment_analysis"
    ENGAGEMENT_METRICS = "engagement_metrics"
    PREDICTIVE_ANALYSIS = "predictive_analysis"
    COLLABORATION_PATTERNS = "collaboration_patterns"
    PERFORMANCE_METRICS = "performance_metrics"
    BEHAVIORAL_INSIGHTS = "behavioral_insights"

class EngagementLevel(Enum):
    """Participant engagement levels"""
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"

class SentimentLabel(Enum):
    """Sentiment classification labels"""
    POSITIVE = "positive"
    NEUTRAL = "neutral"
    NEGATIVE = "negative"
    MIXED = "mixed"

@dataclass
class MeetingInsight:
    """AI-generated meeting insight"""
    insight_id: str
    meeting_id: str
    insight_type: InsightType
    title: str
    description: str
    confidence: float
    data: Dict[str, Any]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class ParticipantBehavior:
    """Participant behavioral analysis"""
    participant_id: str
    meeting_id: str
    speaking_time_seconds: int
    speaking_turns: int
    average_utterance_length: float
    sentiment_score: float
    engagement_score: float
    dominance_score: float
    collaboration_score: float
    interruptions: int
    interruptions_received: int
    questions_asked: int
    responses_provided: int
    sentiment_trend: List[float]
    speaking_rate: float  # words per minute
    vocal_features: Dict[str, float]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class MeetingEngagement:
    """Meeting engagement analysis"""
    meeting_id: str
    overall_engagement_score: float
    average_participant_engagement: float
    engagement_distribution: Dict[EngagementLevel, int]
    attention_score: float
    interaction_rate: float
    collaboration_index: float
    participation_balance: float
    energy_level: float
    momentum_score: float
    retention_score: float
    engagement_timeline: List[Dict[str, Any]]
    metrics: Dict[str, Any]
    created_at: datetime

@dataclass
class PredictiveModel:
    """Predictive analysis model"""
    model_id: str
    model_type: str
    meeting_id: str
    prediction_type: str
    confidence: float
    prediction_data: Dict[str, Any]
    features_used: List[str]
    model_version: str
    accuracy_score: float
    created_at: datetime
    updated_at: datetime

class ZoomAIAnalyticsEngine:
    """Enterprise-grade AI analytics engine for Zoom meetings"""
    
    def __init__(self, db_pool: asyncpg.Pool, openai_api_key: Optional[str] = None):
        self.db_pool = db_pool
        self.openai_api_key = openai_api_key
        
        # Initialize AI models
        self.sentence_transformer = None
        self.openai_client = None
        self.whisper_model = None
        self.tfidf_vectorizer = TfidfVectorizer(max_features=1000, stop_words='english')
        
        # Analytics storage
        self.meeting_insights: Dict[str, List[MeetingInsight]] = defaultdict(list)
        self.participant_behaviors: Dict[str, Dict[str, ParticipantBehavior]] = defaultdict(dict)
        self.meeting_engagements: Dict[str, MeetingEngagement] = {}
        self.predictive_models: Dict[str, List[PredictiveModel]] = defaultdict(list)
        
        # Processing queues
        self.audio_processing_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        self.text_analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self.behavior_analysis_queue: asyncio.Queue = asyncio.Queue(maxsize=200)
        self.insight_generation_queue: asyncio.Queue = asyncio.Queue(maxsize=100)
        
        # Configuration
        self.config = {
            'audio_sample_rate': 16000,
            'audio_chunk_size': 30000,  # 30 seconds
            'min_speaking_duration': 2.0,  # seconds
            'sentiment_analysis_window': 60,  # seconds
            'engagement_calculation_window': 30,  # seconds
            'behavioral_analysis_interval': 60,  # seconds
            'insight_generation_threshold': 10,  # minimum data points
            'max_concurrent_audio_processing': 3,
            'max_concurrent_text_analysis': 5,
            'max_concurrent_insight_generation': 2,
            'ai_cache_ttl': 3600,  # 1 hour
            'model_accuracy_threshold': 0.7
        }
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # Performance metrics
        self.metrics = {
            'insights_generated': 0,
            'audio_segments_processed': 0,
            'text_analyses_completed': 0,
            'behaviors_analyzed': 0,
            'predictions_made': 0,
            'average_processing_time': 0,
            'ai_api_calls': 0,
            'cache_hits': 0,
            'cache_misses': 0
        }
        
        # Initialize AI components
        asyncio.create_task(self._init_ai_components())
    
    async def _init_ai_components(self) -> None:
        """Initialize AI models and components"""
        try:
            # Initialize OpenAI client
            if self.openai_api_key:
                self.openai_client = AsyncOpenAI(api_key=self.openai_api_key)
                logger.info("OpenAI client initialized successfully")
            
            # Initialize sentence transformer
            self.sentence_transformer = SentenceTransformer('all-MiniLM-L6-v2')
            logger.info("Sentence transformer model loaded successfully")
            
            # Initialize Whisper model
            try:
                self.whisper_model = whisper.load_model("base.en")
                logger.info("Whisper model loaded successfully")
            except Exception as e:
                logger.warning(f"Failed to load Whisper model: {e}")
                self.whisper_model = None
            
            logger.info("AI analytics engine components initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize AI components: {e}")
            raise
    
    async def start_processing(self) -> None:
        """Start AI analytics processing"""
        try:
            self.is_running = True
            
            # Start background processing tasks
            self.background_tasks = [
                asyncio.create_task(self._audio_processor()),
                asyncio.create_task(self._text_analyzer()),
                asyncio.create_task(self._behavior_analyzer()),
                asyncio.create_task(self._insight_generator()),
                asyncio.create_task(self._predictive_analyzer()),
                asyncio.create_task(self._metrics_collector()),
                asyncio.create_task(self._cache_cleanup())
            ]
            
            logger.info("AI analytics engine started successfully")
            
        except Exception as e:
            logger.error(f"Failed to start AI analytics engine: {e}")
            raise
    
    async def stop_processing(self) -> None:
        """Stop AI analytics processing"""
        try:
            self.is_running = False
            
            # Cancel background tasks
            for task in self.background_tasks:
                task.cancel()
                try:
                    await task
                except asyncio.CancelledError:
                    pass
            
            logger.info("AI analytics engine stopped successfully")
            
        except Exception as e:
            logger.error(f"Failed to stop AI analytics engine: {e}")
    
    async def process_meeting_audio(self, meeting_id: str, audio_data: bytes, 
                                  participant_id: str, timestamp: datetime) -> Optional[str]:
        """Process meeting audio for transcription and analysis"""
        try:
            audio_task = {
                'meeting_id': meeting_id,
                'participant_id': participant_id,
                'audio_data': audio_data,
                'timestamp': timestamp,
                'task_id': f"{meeting_id}_{participant_id}_{int(timestamp.timestamp())}"
            }
            
            await self.audio_processing_queue.put(audio_task)
            return audio_task['task_id']
            
        except Exception as e:
            logger.error(f"Failed to queue audio processing: {e}")
            return None
    
    async def process_meeting_text(self, meeting_id: str, text: str, 
                                 participant_id: str, timestamp: datetime,
                                 text_type: str = 'transcription') -> Optional[str]:
        """Process meeting text for sentiment and topic analysis"""
        try:
            text_task = {
                'meeting_id': meeting_id,
                'participant_id': participant_id,
                'text': text,
                'text_type': text_type,
                'timestamp': timestamp,
                'task_id': f"{meeting_id}_{participant_id}_{text_type}_{int(timestamp.timestamp())}"
            }
            
            await self.text_analysis_queue.put(text_task)
            return text_task['task_id']
            
        except Exception as e:
            logger.error(f"Failed to queue text analysis: {e}")
            return None
    
    async def generate_meeting_summary(self, meeting_id: str, 
                                   summary_type: str = 'comprehensive') -> Optional[MeetingInsight]:
        """Generate AI-powered meeting summary"""
        try:
            # Get meeting data
            meeting_data = await self._get_meeting_data(meeting_id)
            if not meeting_data:
                return None
            
            # Generate summary based on type
            if summary_type == 'comprehensive':
                summary = await self._generate_comprehensive_summary(meeting_data)
            elif summary_type == 'executive':
                summary = await self._generate_executive_summary(meeting_data)
            elif summary_type == 'action_items':
                summary = await self._generate_action_items_summary(meeting_data)
            else:
                summary = await self._generate_basic_summary(meeting_data)
            
            # Create insight
            insight = MeetingInsight(
                insight_id=f"summary_{meeting_id}_{int(datetime.now(timezone.utc).timestamp())}",
                meeting_id=meeting_id,
                insight_type=InsightType.MEETING_SUMMARY,
                title=summary['title'],
                description=summary['description'],
                confidence=summary['confidence'],
                data=summary['data'],
                metadata={'summary_type': summary_type, 'generated_by': 'ai_analytics'},
                created_at=datetime.now(timezone.utc),
                updated_at=datetime.now(timezone.utc)
            )
            
            # Store insight
            self.meeting_insights[meeting_id].append(insight)
            await self._store_insight(insight)
            
            # Update metrics
            self.metrics['insights_generated'] += 1
            self.metrics['ai_api_calls'] += summary.get('api_calls', 0)
            
            return insight
            
        except Exception as e:
            logger.error(f"Failed to generate meeting summary: {e}")
            return None
    
    async def analyze_participant_engagement(self, meeting_id: str, 
                                         participant_id: str) -> Optional[ParticipantBehavior]:
        """Analyze participant engagement and behavior"""
        try:
            # Get participant data
            participant_data = await self._get_participant_data(meeting_id, participant_id)
            if not participant_data:
                return None
            
            # Analyze behavior
            behavior = await self._analyze_participant_behavior(participant_data)
            
            # Create behavior object
            participant_behavior = ParticipantBehavior(
                participant_id=participant_id,
                meeting_id=meeting_id,
                speaking_time_seconds=behavior['speaking_time_seconds'],
                speaking_turns=behavior['speaking_turns'],
                average_utterance_length=behavior['average_utterance_length'],
                sentiment_score=behavior['sentiment_score'],
                engagement_score=behavior['engagement_score'],
                dominance_score=behavior['dominance_score'],
                collaboration_score=behavior['collaboration_score'],
                interruptions=behavior['interruptions'],
                interruptions_received=behavior['interruptions_received'],
                questions_asked=behavior['questions_asked'],
                responses_provided=behavior['responses_provided'],
                sentiment_trend=behavior['sentiment_trend'],
                speaking_rate=behavior['speaking_rate'],
                vocal_features=behavior['vocal_features'],
                metadata=behavior['metadata'],
                created_at=datetime.now(timezone.utc)
            )
            
            # Store behavior
            if meeting_id not in self.participant_behaviors:
                self.participant_behaviors[meeting_id] = {}
            
            self.participant_behaviors[meeting_id][participant_id] = participant_behavior
            await self._store_participant_behavior(participant_behavior)
            
            # Update metrics
            self.metrics['behaviors_analyzed'] += 1
            
            return participant_behavior
            
        except Exception as e:
            logger.error(f"Failed to analyze participant engagement: {e}")
            return None
    
    async def calculate_meeting_engagement(self, meeting_id: str) -> Optional[MeetingEngagement]:
        """Calculate overall meeting engagement metrics"""
        try:
            # Get all participant behaviors
            participant_behaviors = self.participant_behaviors.get(meeting_id, {})
            if not participant_behaviors:
                return None
            
            # Calculate engagement metrics
            engagement = await self._calculate_engagement_metrics(participant_behaviors)
            
            # Create engagement object
            meeting_engagement = MeetingEngagement(
                meeting_id=meeting_id,
                overall_engagement_score=engagement['overall_engagement_score'],
                average_participant_engagement=engagement['average_participant_engagement'],
                engagement_distribution=engagement['engagement_distribution'],
                attention_score=engagement['attention_score'],
                interaction_rate=engagement['interaction_rate'],
                collaboration_index=engagement['collaboration_index'],
                participation_balance=engagement['participation_balance'],
                energy_level=engagement['energy_level'],
                momentum_score=engagement['momentum_score'],
                retention_score=engagement['retention_score'],
                engagement_timeline=engagement['engagement_timeline'],
                metrics=engagement['metrics'],
                created_at=datetime.now(timezone.utc)
            )
            
            # Store engagement
            self.meeting_engagements[meeting_id] = meeting_engagement
            await self._store_meeting_engagement(meeting_engagement)
            
            return meeting_engagement
            
        except Exception as e:
            logger.error(f"Failed to calculate meeting engagement: {e}")
            return None
    
    async def predict_meeting_outcomes(self, meeting_id: str, 
                                    prediction_types: List[str] = None) -> List[PredictiveModel]:
        """Generate predictive analytics for meeting outcomes"""
        try:
            if prediction_types is None:
                prediction_types = ['attendance', 'engagement', 'decision_making', 'action_item_completion']
            
            predictions = []
            
            for prediction_type in prediction_types:
                # Generate prediction
                prediction = await self._generate_prediction(meeting_id, prediction_type)
                
                if prediction:
                    predictive_model = PredictiveModel(
                        model_id=f"prediction_{meeting_id}_{prediction_type}_{int(datetime.now(timezone.utc).timestamp())}",
                        model_type=prediction['model_type'],
                        meeting_id=meeting_id,
                        prediction_type=prediction_type,
                        confidence=prediction['confidence'],
                        prediction_data=prediction['prediction_data'],
                        features_used=prediction['features_used'],
                        model_version=prediction['model_version'],
                        accuracy_score=prediction['accuracy_score'],
                        created_at=datetime.now(timezone.utc),
                        updated_at=datetime.now(timezone.utc)
                    )
                    
                    predictions.append(predictive_model)
                    self.predictive_models[meeting_id].append(predictive_model)
                    await self._store_predictive_model(predictive_model)
                    
                    self.metrics['predictions_made'] += 1
            
            return predictions
            
        except Exception as e:
            logger.error(f"Failed to predict meeting outcomes: {e}")
            return []
    
    # Background Processing Tasks
    async def _audio_processor(self) -> None:
        """Process audio queue for transcription"""
        while self.is_running:
            try:
                # Get audio task
                audio_task = await asyncio.wait_for(
                    self.audio_processing_queue.get(),
                    timeout=1.0
                )
                
                start_time = datetime.now(timezone.utc)
                
                # Process audio
                transcription = await self._transcribe_audio(audio_task['audio_data'])
                
                if transcription:
                    # Queue for text analysis
                    await self.text_analysis_queue.put({
                        'meeting_id': audio_task['meeting_id'],
                        'participant_id': audio_task['participant_id'],
                        'text': transcription,
                        'text_type': 'transcription',
                        'timestamp': audio_task['timestamp']
                    })
                
                # Update metrics
                processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
                self.metrics['audio_segments_processed'] += 1
                self._update_average_processing_time(processing_time)
                
                logger.debug(f"Processed audio segment: {audio_task['task_id']}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in audio processor: {e}")
    
    async def _text_analyzer(self) -> None:
        """Process text analysis queue"""
        while self.is_running:
            try:
                # Get text task
                text_task = await asyncio.wait_for(
                    self.text_analysis_queue.get(),
                    timeout=1.0
                )
                
                # Analyze text
                analysis = await self._analyze_text(
                    text_task['text'],
                    text_task['participant_id'],
                    text_task['meeting_id']
                )
                
                # Store analysis
                await self._store_text_analysis(text_task['task_id'], analysis)
                
                # Update metrics
                self.metrics['text_analyses_completed'] += 1
                
                logger.debug(f"Analyzed text: {text_task['task_id']}")
                
            except asyncio.TimeoutError:
                continue
            except Exception as e:
                logger.error(f"Error in text analyzer: {e}")
    
    async def _behavior_analyzer(self) -> None:
        """Analyze participant behaviors"""
        while self.is_running:
            try:
                await asyncio.sleep(self.config['behavioral_analysis_interval'])
                
                # Get active meetings
                active_meetings = await self._get_active_meetings()
                
                for meeting_id in active_meetings:
                    # Analyze all participants
                    participants = await self._get_meeting_participants(meeting_id)
                    
                    for participant_id in participants:
                        if participant_id not in self.participant_behaviors.get(meeting_id, {}):
                            await self.analyze_participant_engagement(meeting_id, participant_id)
            
            except Exception as e:
                logger.error(f"Error in behavior analyzer: {e}")
    
    async def _insight_generator(self) -> None:
        """Generate AI insights"""
        while self.is_running:
            try:
                await asyncio.sleep(300)  # Generate insights every 5 minutes
                
                # Get meetings with sufficient data
                ready_meetings = await self._get_meetings_ready_for_insights()
                
                for meeting_id in ready_meetings:
                    # Generate different types of insights
                    await self._generate_sentiment_insights(meeting_id)
                    await self._generate_collaboration_insights(meeting_id)
                    await self._generate_engagement_insights(meeting_id)
                    
                    # Check if summary should be generated
                    last_summary = await self._get_last_summary_time(meeting_id)
                    if not last_summary or (datetime.now(timezone.utc) - last_summary) > timedelta(hours=1):
                        await self.generate_meeting_summary(meeting_id, 'comprehensive')
            
            except Exception as e:
                logger.error(f"Error in insight generator: {e}")
    
    async def _predictive_analyzer(self) -> None:
        """Generate predictive analytics"""
        while self.is_running:
            try:
                await asyncio.sleep(600)  # Generate predictions every 10 minutes
                
                # Get meetings for prediction
                prediction_meetings = await self._get_meetings_for_prediction()
                
                for meeting_id in prediction_meetings:
                    await self.predict_meeting_outcomes(meeting_id)
            
            except Exception as e:
                logger.error(f"Error in predictive analyzer: {e}")
    
    async def _metrics_collector(self) -> None:
        """Collect and report AI metrics"""
        while self.is_running:
            try:
                await asyncio.sleep(60)  # Collect metrics every minute
                
                # Calculate cache hit rate
                cache_hit_rate = (
                    self.metrics['cache_hits'] / 
                    max(self.metrics['cache_hits'] + self.metrics['cache_misses'], 1)
                )
                
                # Store metrics
                metrics_data = {
                    **self.metrics,
                    'cache_hit_rate': cache_hit_rate,
                    'timestamp': datetime.now(timezone.utc).isoformat()
                }
                
                await self._store_ai_metrics(metrics_data)
                
                logger.info(f"AI Analytics Metrics: {self.metrics}")
                
            except Exception as e:
                logger.error(f"Error in metrics collector: {e}")
    
    async def _cache_cleanup(self) -> None:
        """Clean up AI cache"""
        while self.is_running:
            try:
                await asyncio.sleep(1800)  # Clean up every 30 minutes
                
                # Implement cache cleanup logic
                await self._cleanup_ai_cache()
                
            except Exception as e:
                logger.error(f"Error in cache cleanup: {e}")
    
    # AI Analysis Methods
    async def _transcribe_audio(self, audio_data: bytes) -> Optional[str]:
        """Transcribe audio using Whisper"""
        try:
            if not self.whisper_model:
                return None
            
            # Save audio to temporary file
            temp_file = f"/tmp/temp_audio_{datetime.now().timestamp()}.wav"
            
            # Convert audio data to proper format (this would need proper audio processing)
            with open(temp_file, "wb") as f:
                f.write(audio_data)
            
            # Transcribe
            result = self.whisper_model.transcribe(temp_file)
            transcription = result.get('text', '')
            
            # Clean up temporary file
            os.remove(temp_file)
            
            return transcription
            
        except Exception as e:
            logger.error(f"Failed to transcribe audio: {e}")
            return None
    
    async def _analyze_text(self, text: str, participant_id: str, 
                           meeting_id: str) -> Dict[str, Any]:
        """Analyze text for sentiment, topics, and insights"""
        try:
            analysis = {
                'text': text,
                'participant_id': participant_id,
                'meeting_id': meeting_id,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'sentiment': await self._analyze_sentiment(text),
                'topics': await self._extract_topics(text),
                'entities': await self._extract_entities(text),
                'language': await self._detect_language(text),
                'emotions': await self._detect_emotions(text)
            }
            
            return analysis
            
        except Exception as e:
            logger.error(f"Failed to analyze text: {e}")
            return {}
    
    async def _analyze_sentiment(self, text: str) -> Dict[str, Any]:
        """Analyze sentiment of text"""
        try:
            if not self.openai_client:
                return {'sentiment': 'neutral', 'confidence': 0.5}
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze the sentiment of the following text and provide a sentiment score from -1 (very negative) to 1 (very positive). Return as JSON: {sentiment: 'positive/neutral/negative', score: float, confidence: float}"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=100
            )
            
            result = json.loads(response.choices[0].message.content)
            self.metrics['ai_api_calls'] += 1
            
            return result
            
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return {'sentiment': 'neutral', 'confidence': 0.0}
    
    async def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text"""
        try:
            if not self.openai_client:
                return []
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract the main topics from the following text. Return as a JSON array of strings: [topic1, topic2, ...]"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=150
            )
            
            topics = json.loads(response.choices[0].message.content)
            self.metrics['ai_api_calls'] += 1
            
            return topics
            
        except Exception as e:
            logger.error(f"Failed to extract topics: {e}")
            return []
    
    async def _extract_entities(self, text: str) -> List[Dict[str, str]]:
        """Extract named entities from text"""
        try:
            if not self.openai_client:
                return []
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract named entities (people, organizations, locations, dates) from the following text. Return as JSON array: [{type: string, value: string}, ...]"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=200
            )
            
            entities = json.loads(response.choices[0].message.content)
            self.metrics['ai_api_calls'] += 1
            
            return entities
            
        except Exception as e:
            logger.error(f"Failed to extract entities: {e}")
            return []
    
    async def _detect_language(self, text: str) -> str:
        """Detect language of text"""
        try:
            # Simple language detection (in production, would use more sophisticated method)
            if not text:
                return 'unknown'
            
            # Check for common English words
            common_words = ['the', 'and', 'is', 'to', 'a', 'in', 'that', 'have', 'i', 'it', 'for']
            word_count = len(text.split())
            english_word_count = sum(1 for word in text.lower().split() if word in common_words)
            
            if word_count > 0 and english_word_count / word_count > 0.3:
                return 'english'
            else:
                return 'other'
            
        except Exception as e:
            logger.error(f"Failed to detect language: {e}")
            return 'unknown'
    
    async def _detect_emotions(self, text: str) -> Dict[str, float]:
        """Detect emotions in text"""
        try:
            if not self.openai_client:
                return {'neutral': 1.0}
            
            response = await self.openai_client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {
                        "role": "system",
                        "content": "Analyze emotions in the following text. Return as JSON with emotion scores: {joy: float, sadness: float, anger: float, fear: float, surprise: float, disgust: float}"
                    },
                    {
                        "role": "user",
                        "content": text
                    }
                ],
                max_tokens=150
            )
            
            emotions = json.loads(response.choices[0].message.content)
            self.metrics['ai_api_calls'] += 1
            
            return emotions
            
        except Exception as e:
            logger.error(f"Failed to detect emotions: {e}")
            return {'neutral': 1.0}
    
    # Database Operations
    async def _init_database(self) -> None:
        """Initialize AI analytics database tables"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create meeting insights table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_meeting_insights (
                        insight_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        insight_type VARCHAR(100) NOT NULL,
                        title TEXT NOT NULL,
                        description TEXT NOT NULL,
                        confidence NUMERIC(3,2) NOT NULL,
                        data JSONB DEFAULT '{}'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create participant behaviors table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_participant_behaviors (
                        participant_id VARCHAR(255) NOT NULL,
                        meeting_id VARCHAR(255) NOT NULL,
                        speaking_time_seconds INTEGER,
                        speaking_turns INTEGER,
                        average_utterance_length NUMERIC(8,2),
                        sentiment_score NUMERIC(4,3),
                        engagement_score NUMERIC(3,2),
                        dominance_score NUMERIC(3,2),
                        collaboration_score NUMERIC(3,2),
                        interruptions INTEGER,
                        interruptions_received INTEGER,
                        questions_asked INTEGER,
                        responses_provided INTEGER,
                        sentiment_trend JSONB DEFAULT '[]'::jsonb,
                        speaking_rate NUMERIC(6,2),
                        vocal_features JSONB DEFAULT '{}'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        PRIMARY KEY (participant_id, meeting_id)
                    );
                """)
                
                # Create meeting engagements table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_meeting_engagements (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        overall_engagement_score NUMERIC(3,2) NOT NULL,
                        average_participant_engagement NUMERIC(3,2) NOT NULL,
                        engagement_distribution JSONB DEFAULT '{}'::jsonb,
                        attention_score NUMERIC(3,2) NOT NULL,
                        interaction_rate NUMERIC(3,2) NOT NULL,
                        collaboration_index NUMERIC(3,2) NOT NULL,
                        participation_balance NUMERIC(3,2) NOT NULL,
                        energy_level NUMERIC(3,2) NOT NULL,
                        momentum_score NUMERIC(3,2) NOT NULL,
                        retention_score NUMERIC(3,2) NOT NULL,
                        engagement_timeline JSONB DEFAULT '[]'::jsonb,
                        metrics JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create predictive models table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_predictive_models (
                        model_id VARCHAR(255) PRIMARY KEY,
                        model_type VARCHAR(100) NOT NULL,
                        meeting_id VARCHAR(255) NOT NULL,
                        prediction_type VARCHAR(100) NOT NULL,
                        confidence NUMERIC(3,2) NOT NULL,
                        prediction_data JSONB DEFAULT '{}'::jsonb,
                        features_used JSONB DEFAULT '[]'::jsonb,
                        model_version VARCHAR(50) NOT NULL,
                        accuracy_score NUMERIC(3,2) NOT NULL,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create text analyses table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_text_analyses (
                        task_id VARCHAR(255) PRIMARY KEY,
                        meeting_id VARCHAR(255) NOT NULL,
                        participant_id VARCHAR(255) NOT NULL,
                        text TEXT NOT NULL,
                        text_type VARCHAR(50) NOT NULL,
                        analysis JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create AI metrics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_ai_metrics (
                        metrics_id VARCHAR(255) PRIMARY KEY,
                        insights_generated INTEGER DEFAULT 0,
                        audio_segments_processed INTEGER DEFAULT 0,
                        text_analyses_completed INTEGER DEFAULT 0,
                        behaviors_analyzed INTEGER DEFAULT 0,
                        predictions_made INTEGER DEFAULT 0,
                        average_processing_time NUMERIC(8,3) DEFAULT 0,
                        ai_api_calls INTEGER DEFAULT 0,
                        cache_hits INTEGER DEFAULT 0,
                        cache_misses INTEGER DEFAULT 0,
                        cache_hit_rate NUMERIC(4,3) DEFAULT 0,
                        timestamp TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_insights_meeting ON zoom_meeting_insights(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_insights_type ON zoom_meeting_insights(insight_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_insights_created ON zoom_meeting_insights(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_behaviors_meeting ON zoom_participant_behaviors(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_behaviors_participant ON zoom_participant_behaviors(participant_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participant_behaviors_engagement ON zoom_participant_behaviors(engagement_score);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_engagements_overall ON zoom_meeting_engagements(overall_engagement_score);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_meeting_engagements_created ON zoom_meeting_engagements(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_predictive_models_meeting ON zoom_predictive_models(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_predictive_models_type ON zoom_predictive_models(prediction_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_predictive_models_confidence ON zoom_predictive_models(confidence);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_text_analyses_meeting ON zoom_text_analyses(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_text_analyses_participant ON zoom_text_analyses(participant_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_text_analyses_type ON zoom_text_analyses(text_type);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_ai_metrics_timestamp ON zoom_ai_metrics(timestamp);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("AI analytics database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize AI analytics database: {e}")
    
    # Utility Methods
    def _update_average_processing_time(self, processing_time: float) -> None:
        """Update average processing time metric"""
        total_events = (
            self.metrics['audio_segments_processed'] + 
            self.metrics['text_analyses_completed'] + 
            self.metrics['behaviors_analyzed']
        )
        
        if total_events > 0:
            self.metrics['average_processing_time'] = (
                (self.metrics['average_processing_time'] * (total_events - 1) + processing_time) / 
                total_events
            )
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get AI analytics metrics"""
        return self.metrics.copy()
    
    def get_meeting_insights(self, meeting_id: str) -> List[MeetingInsight]:
        """Get insights for a specific meeting"""
        return self.meeting_insights.get(meeting_id, [])
    
    def get_participant_behavior(self, meeting_id: str, participant_id: str) -> Optional[ParticipantBehavior]:
        """Get behavior for a specific participant"""
        return self.participant_behaviors.get(meeting_id, {}).get(participant_id)
    
    def get_meeting_engagement(self, meeting_id: str) -> Optional[MeetingEngagement]:
        """Get engagement for a specific meeting"""
        return self.meeting_engagements.get(meeting_id)
    
    def get_predictions(self, meeting_id: str) -> List[PredictiveModel]:
        """Get predictions for a specific meeting"""
        return self.predictive_models.get(meeting_id, [])