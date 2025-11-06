"""
📊 Zoom Advanced Meeting Analytics
Comprehensive analytics and business intelligence for Zoom meetings
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
import plotly.graph_objects as go
import plotly.express as px
from sklearn.preprocessing import StandardScaler
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from scipy import stats
import networkx as nx

from zoom_ai_analytics_engine import (
    MeetingInsight, ParticipantBehavior, MeetingEngagement,
    InsightType, EngagementLevel, SentimentLabel
)

logger = logging.getLogger(__name__)

class MetricType(Enum):
    """Analytics metric types"""
    PARTICIPATION = "participation"
    ENGAGEMENT = "engagement"
    SPEAKING_TIME = "speaking_time"
    SENTIMENT = "sentiment"
    COLLABORATION = "collaboration"
    INTERACTION = "interaction"
    DOMINANCE = "dominance"
    ATTENTION = "attention"
    PRODUCTIVITY = "productivity"
    SATISFACTION = "satisfaction"

class TimeGranularity(Enum):
    """Time granularity for analytics"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

class ComparisonType(Enum):
    """Comparison types for analytics"""
    PERIOD_OVER_PERIOD = "period_over_period"
    YEAR_OVER_YEAR = "year_over_year"
    MEETING_OVER_MEETING = "meeting_over_meeting"
    PARTICIPANT_OVER_PARTICIPANT = "participant_over_participant"
    ACCOUNT_OVER_ACCOUNT = "account_over_account"

@dataclass
class AnalyticsMetric:
    """Analytics metric data structure"""
    metric_id: str
    metric_type: MetricType
    name: str
    description: str
    value: float
    unit: str
    change: float
    change_percentage: float
    trend: str  # up, down, stable
    data_points: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime
    updated_at: datetime

@dataclass
class ParticipationAnalytics:
    """Participation analytics data"""
    meeting_id: str
    total_participants: int
    speaking_participants: int
    silent_participants: int
    average_participation_rate: float
    participation_distribution: Dict[str, int]
    speaking_time_distribution: Dict[str, float]
    interaction_frequency: Dict[str, int]
    participation_heatmap: List[List[int]]
    speaking_patterns: Dict[str, List[float]]
    response_times: Dict[str, List[float]]
    question_answer_pairs: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class EngagementAnalytics:
    """Engagement analytics data"""
    meeting_id: str
    overall_engagement_score: float
    engagement_timeline: List[Dict[str, Any]]
    peak_engagement_periods: List[Tuple[datetime, datetime]]
    low_engagement_periods: List[Tuple[datetime, datetime]]
    engagement_distribution: Dict[EngagementLevel, int]
    attention_scores: List[float]
    energy_levels: List[float]
    momentum_scores: List[float]
    retention_scores: List[float]
    engagement_drivers: List[Dict[str, Any]]
    engagement_barriers: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class SentimentAnalytics:
    """Sentiment analytics data"""
    meeting_id: str
    overall_sentiment_score: float
    sentiment_timeline: List[Dict[str, Any]]
    sentiment_distribution: Dict[SentimentLabel, int]
    sentiment_trends: Dict[str, float]
    sentiment_shifts: List[Dict[str, Any]]
    emotional_intensity: List[float]
    sentiment_volatility: float
    sentiment_correlations: Dict[str, float]
    sentiment_drivers: List[Dict[str, Any]]
    sentiment_topics: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class CollaborationAnalytics:
    """Collaboration analytics data"""
    meeting_id: str
    collaboration_index: float
    interaction_network: Dict[str, List[str]]
    collaboration_pairs: List[Dict[str, Any]]
    knowledge_sharing_metrics: Dict[str, float]
    idea_generation_count: int
    decision_making_speed: float
    consensus_reaching_time: float
    conflict_resolution_metrics: Dict[str, Any]
    cross_functional_collaboration: float
    collaboration_quality_score: float
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class ProductivityAnalytics:
    """Productivity analytics data"""
    meeting_id: str
    productivity_score: float
    time_efficiency: float
    decision_count: int
    action_items_count: int
    goal_completion_rate: float
    agenda_adherence: float
    time_on_topic: float
    tangent_duration: float
    focus_score: float
    output_quality_score: float
    productivity_barriers: List[Dict[str, Any]]
    productivity_enablers: List[Dict[str, Any]]
    metadata: Dict[str, Any]
    created_at: datetime

@dataclass
class BusinessImpactAnalytics:
    """Business impact analytics data"""
    meeting_id: str
    roi_score: float
    cost_benefit_analysis: Dict[str, float]
    business_value_generated: float
    strategic_alignment: float
    stakeholder_satisfaction: float
    innovation_score: float
    risk_mitigation_impact: float
    market_opportunity_value: float
    customer_impact: float
    operational_efficiency_impact: float
    metadata: Dict[str, Any]
    created_at: datetime

class ZoomAdvancedAnalytics:
    """Advanced analytics engine for Zoom meetings"""
    
    def __init__(self, db_pool: asyncpg.Pool, ai_analytics_engine=None):
        self.db_pool = db_pool
        self.ai_analytics_engine = ai_analytics_engine
        
        # Analytics storage
        self.metrics: Dict[str, List[AnalyticsMetric]] = defaultdict(list)
        self.participation_analytics: Dict[str, ParticipationAnalytics] = {}
        self.engagement_analytics: Dict[str, EngagementAnalytics] = {}
        self.sentiment_analytics: Dict[str, SentimentAnalytics] = {}
        self.collaboration_analytics: Dict[str, CollaborationAnalytics] = {}
        self.productivity_analytics: Dict[str, ProductivityAnalytics] = {}
        self.business_impact_analytics: Dict[str, BusinessImpactAnalytics] = {}
        
        # Analytics configuration
        self.config = {
            'min_participants_for_analytics': 2,
            'min_meeting_duration_minutes': 5,
            'speaking_time_threshold_seconds': 5,
            'engagement_calculation_window_minutes': 5,
            'sentiment_analysis_window_minutes': 2,
            'collaboration_interaction_threshold': 3,
            'productivity_metrics_window_minutes': 10,
            'business_impact_calculation_days': 30,
            'analytics_cache_ttl_hours': 24,
            'comparison_periods_days': 30,
            'trend_analysis_days': 90,
            'batch_size': 100,
            'max_historical_days': 365
        }
        
        # Background tasks
        self.background_tasks: List[asyncio.Task] = []
        self.is_running = False
        
        # Performance metrics
        self.performance_metrics = {
            'analytics_calculated': 0,
            'metrics_generated': 0,
            'reports_created': 0,
            'comparisons_made': 0,
            'predictions_generated': 0,
            'average_processing_time': 0,
            'cache_hit_rate': 0
        }
        
        # Initialize database
        asyncio.create_task(self._init_database())
    
    async def _init_database(self) -> None:
        """Initialize analytics database tables"""
        if not self.db_pool:
            logger.warning("Database pool not available for analytics")
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Create analytics metrics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_analytics_metrics (
                        metric_id VARCHAR(255) PRIMARY KEY,
                        metric_type VARCHAR(100) NOT NULL,
                        name VARCHAR(255) NOT NULL,
                        description TEXT,
                        value NUMERIC(15,5) NOT NULL,
                        unit VARCHAR(50) DEFAULT 'count',
                        change NUMERIC(15,5),
                        change_percentage NUMERIC(5,2),
                        trend VARCHAR(20) DEFAULT 'stable',
                        data_points JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create participation analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_participation_analytics (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        total_participants INTEGER NOT NULL,
                        speaking_participants INTEGER,
                        silent_participants INTEGER,
                        average_participation_rate NUMERIC(5,2),
                        participation_distribution JSONB DEFAULT '{}'::jsonb,
                        speaking_time_distribution JSONB DEFAULT '{}'::jsonb,
                        interaction_frequency JSONB DEFAULT '{}'::jsonb,
                        participation_heatmap JSONB DEFAULT '[]'::jsonb,
                        speaking_patterns JSONB DEFAULT '{}'::jsonb,
                        response_times JSONB DEFAULT '{}'::jsonb,
                        question_answer_pairs JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create engagement analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_engagement_analytics (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        overall_engagement_score NUMERIC(5,2) NOT NULL,
                        engagement_timeline JSONB DEFAULT '[]'::jsonb,
                        peak_engagement_periods JSONB DEFAULT '[]'::jsonb,
                        low_engagement_periods JSONB DEFAULT '[]'::jsonb,
                        engagement_distribution JSONB DEFAULT '{}'::jsonb,
                        attention_scores JSONB DEFAULT '[]'::jsonb,
                        energy_levels JSONB DEFAULT '[]'::jsonb,
                        momentum_scores JSONB DEFAULT '[]'::jsonb,
                        retention_scores JSONB DEFAULT '[]'::jsonb,
                        engagement_drivers JSONB DEFAULT '[]'::jsonb,
                        engagement_barriers JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create sentiment analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_sentiment_analytics (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        overall_sentiment_score NUMERIC(4,3) NOT NULL,
                        sentiment_timeline JSONB DEFAULT '[]'::jsonb,
                        sentiment_distribution JSONB DEFAULT '{}'::jsonb,
                        sentiment_trends JSONB DEFAULT '{}'::jsonb,
                        sentiment_shifts JSONB DEFAULT '[]'::jsonb,
                        emotional_intensity JSONB DEFAULT '[]'::jsonb,
                        sentiment_volatility NUMERIC(5,3),
                        sentiment_correlations JSONB DEFAULT '{}'::jsonb,
                        sentiment_drivers JSONB DEFAULT '[]'::jsonb,
                        sentiment_topics JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create collaboration analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_collaboration_analytics (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        collaboration_index NUMERIC(5,2) NOT NULL,
                        interaction_network JSONB DEFAULT '{}'::jsonb,
                        collaboration_pairs JSONB DEFAULT '[]'::jsonb,
                        knowledge_sharing_metrics JSONB DEFAULT '{}'::jsonb,
                        idea_generation_count INTEGER DEFAULT 0,
                        decision_making_speed NUMERIC(8,2),
                        consensus_reaching_time NUMERIC(8,2),
                        conflict_resolution_metrics JSONB DEFAULT '{}'::jsonb,
                        cross_functional_collaboration NUMERIC(5,2),
                        collaboration_quality_score NUMERIC(5,2),
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create productivity analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_productivity_analytics (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        productivity_score NUMERIC(5,2) NOT NULL,
                        time_efficiency NUMERIC(5,2),
                        decision_count INTEGER DEFAULT 0,
                        action_items_count INTEGER DEFAULT 0,
                        goal_completion_rate NUMERIC(5,2),
                        agenda_adherence NUMERIC(5,2),
                        time_on_topic NUMERIC(5,2),
                        tangent_duration NUMERIC(8,2) DEFAULT 0,
                        focus_score NUMERIC(5,2),
                        output_quality_score NUMERIC(5,2),
                        productivity_barriers JSONB DEFAULT '[]'::jsonb,
                        productivity_enablers JSONB DEFAULT '[]'::jsonb,
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create business impact analytics table
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS zoom_business_impact_analytics (
                        meeting_id VARCHAR(255) PRIMARY KEY,
                        roi_score NUMERIC(5,2) NOT NULL,
                        cost_benefit_analysis JSONB DEFAULT '{}'::jsonb,
                        business_value_generated NUMERIC(15,2) DEFAULT 0,
                        strategic_alignment NUMERIC(5,2),
                        stakeholder_satisfaction NUMERIC(5,2),
                        innovation_score NUMERIC(5,2),
                        risk_mitigation_impact NUMERIC(5,2),
                        market_opportunity_value NUMERIC(15,2) DEFAULT 0,
                        customer_impact NUMERIC(5,2),
                        operational_efficiency_impact NUMERIC(5,2),
                        metadata JSONB DEFAULT '{}'::jsonb,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                    );
                """)
                
                # Create indexes
                indexes = [
                    "CREATE INDEX IF NOT EXISTS idx_zoom_analytics_metrics_type ON zoom_analytics_metrics(metric_type);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_analytics_metrics_created ON zoom_analytics_metrics(created_at);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_analytics_metrics_updated ON zoom_analytics_metrics(updated_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participation_analytics_meeting ON zoom_participation_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_participation_analytics_created ON zoom_participation_analytics(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_engagement_analytics_meeting ON zoom_engagement_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_engagement_analytics_score ON zoom_engagement_analytics(overall_engagement_score);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_engagement_analytics_created ON zoom_engagement_analytics(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_sentiment_analytics_meeting ON zoom_sentiment_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_sentiment_analytics_score ON zoom_sentiment_analytics(overall_sentiment_score);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_sentiment_analytics_created ON zoom_sentiment_analytics(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_collaboration_analytics_meeting ON zoom_collaboration_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_collaboration_analytics_index ON zoom_collaboration_analytics(collaboration_index);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_collaboration_analytics_created ON zoom_collaboration_analytics(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_productivity_analytics_meeting ON zoom_productivity_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_productivity_analytics_score ON zoom_productivity_analytics(productivity_score);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_productivity_analytics_created ON zoom_productivity_analytics(created_at);",
                    
                    "CREATE INDEX IF NOT EXISTS idx_zoom_business_impact_analytics_meeting ON zoom_business_impact_analytics(meeting_id);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_business_impact_analytics_roi ON zoom_business_impact_analytics(roi_score);",
                    "CREATE INDEX IF NOT EXISTS idx_zoom_business_impact_analytics_created ON zoom_business_impact_analytics(created_at);"
                ]
                
                for index_sql in indexes:
                    await conn.execute(index_sql)
                
                logger.info("Advanced analytics database tables initialized successfully")
                
        except Exception as e:
            logger.error(f"Failed to initialize advanced analytics database: {e}")
    
    async def calculate_meeting_analytics(self, meeting_id: str) -> Dict[str, Any]:
        """Calculate comprehensive analytics for a meeting"""
        try:
            start_time = datetime.now(timezone.utc)
            
            # Get meeting data
            meeting_data = await self._get_meeting_data(meeting_id)
            if not meeting_data:
                return {'error': 'Meeting not found'}
            
            # Calculate all analytics
            analytics_results = {}
            
            # Participation Analytics
            participation = await self._calculate_participation_analytics(meeting_data)
            if participation:
                analytics_results['participation'] = asdict(participation)
                self.participation_analytics[meeting_id] = participation
            
            # Engagement Analytics
            engagement = await self._calculate_engagement_analytics(meeting_data)
            if engagement:
                analytics_results['engagement'] = asdict(engagement)
                self.engagement_analytics[meeting_id] = engagement
            
            # Sentiment Analytics
            sentiment = await self._calculate_sentiment_analytics(meeting_data)
            if sentiment:
                analytics_results['sentiment'] = asdict(sentiment)
                self.sentiment_analytics[meeting_id] = sentiment
            
            # Collaboration Analytics
            collaboration = await self._calculate_collaboration_analytics(meeting_data)
            if collaboration:
                analytics_results['collaboration'] = asdict(collaboration)
                self.collaboration_analytics[meeting_id] = collaboration
            
            # Productivity Analytics
            productivity = await self._calculate_productivity_analytics(meeting_data)
            if productivity:
                analytics_results['productivity'] = asdict(productivity)
                self.productivity_analytics[meeting_id] = productivity
            
            # Business Impact Analytics
            business_impact = await self._calculate_business_impact_analytics(meeting_data)
            if business_impact:
                analytics_results['business_impact'] = asdict(business_impact)
                self.business_impact_analytics[meeting_id] = business_impact
            
            # Store analytics in database
            await self._store_analytics(meeting_id, analytics_results)
            
            # Generate insights
            insights = await self._generate_comprehensive_insights(meeting_id, analytics_results)
            analytics_results['insights'] = insights
            
            # Update performance metrics
            processing_time = (datetime.now(timezone.utc) - start_time).total_seconds()
            self.performance_metrics['analytics_calculated'] += 1
            self._update_average_processing_time(processing_time)
            
            return analytics_results
            
        except Exception as e:
            logger.error(f"Failed to calculate meeting analytics: {e}")
            return {'error': str(e)}
    
    async def _calculate_participation_analytics(self, meeting_data: Dict[str, Any]) -> Optional[ParticipationAnalytics]:
        """Calculate participation analytics"""
        try:
            meeting_id = meeting_data['meeting_id']
            participants = meeting_data.get('participants', [])
            
            if len(participants) < self.config['min_participants_for_analytics']:
                return None
            
            # Calculate participation metrics
            total_participants = len(participants)
            speaking_participants = sum(1 for p in participants if p.get('speaking_time_seconds', 0) > 0)
            silent_participants = total_participants - speaking_participants
            
            # Speaking time distribution
            speaking_time_distribution = {}
            for participant in participants:
                participant_id = participant['id']
                speaking_time_distribution[participant_id] = participant.get('speaking_time_seconds', 0)
            
            # Interaction frequency
            interaction_frequency = {}
            for participant in participants:
                participant_id = participant['id']
                interaction_frequency[participant_id] = participant.get('interactions_count', 0)
            
            # Participation rate
            average_participation_rate = speaking_participants / total_participants
            
            # Participation distribution
            participation_distribution = {
                'high': sum(1 for p in participants if p.get('speaking_time_seconds', 0) > 300),  # > 5 minutes
                'medium': sum(1 for p in participants if 60 < p.get('speaking_time_seconds', 0) <= 300),  # 1-5 minutes
                'low': sum(1 for p in participants if 10 < p.get('speaking_time_seconds', 0) <= 60),  # 10 seconds - 1 minute
                'very_low': sum(1 for p in participants if p.get('speaking_time_seconds', 0) <= 10)  # <= 10 seconds
            }
            
            # Generate participation heatmap (simplified)
            participation_heatmap = self._generate_participation_heatmap(participants)
            
            # Speaking patterns
            speaking_patterns = self._analyze_speaking_patterns(participants)
            
            # Response times
            response_times = self._calculate_response_times(participants)
            
            # Question-answer pairs
            question_answer_pairs = self._extract_question_answer_pairs(meeting_data)
            
            participation_analytics = ParticipationAnalytics(
                meeting_id=meeting_id,
                total_participants=total_participants,
                speaking_participants=speaking_participants,
                silent_participants=silent_participants,
                average_participation_rate=average_participation_rate,
                participation_distribution=participation_distribution,
                speaking_time_distribution=speaking_time_distribution,
                interaction_frequency=interaction_frequency,
                participation_heatmap=participation_heatmap,
                speaking_patterns=speaking_patterns,
                response_times=response_times,
                question_answer_pairs=question_answer_pairs,
                metadata={
                    'calculation_time': datetime.now(timezone.utc).isoformat(),
                    'participant_count': total_participants
                },
                created_at=datetime.now(timezone.utc)
            )
            
            return participation_analytics
            
        except Exception as e:
            logger.error(f"Failed to calculate participation analytics: {e}")
            return None
    
    async def _calculate_engagement_analytics(self, meeting_data: Dict[str, Any]) -> Optional[EngagementAnalytics]:
        """Calculate engagement analytics"""
        try:
            meeting_id = meeting_data['meeting_id']
            participants = meeting_data.get('participants', [])
            
            if len(participants) < self.config['min_participants_for_analytics']:
                return None
            
            # Calculate overall engagement score
            engagement_scores = [p.get('engagement_score', 0) for p in participants]
            overall_engagement_score = np.mean(engagement_scores) if engagement_scores else 0
            
            # Generate engagement timeline
            engagement_timeline = self._generate_engagement_timeline(participants)
            
            # Identify peak and low engagement periods
            peak_periods, low_periods = self._identify_engagement_periods(engagement_timeline)
            
            # Engagement distribution
            engagement_distribution = self._calculate_engagement_distribution(engagement_scores)
            
            # Calculate attention scores
            attention_scores = self._calculate_attention_scores(participants)
            
            # Calculate energy levels
            energy_levels = self._calculate_energy_levels(participants)
            
            # Calculate momentum scores
            momentum_scores = self._calculate_momentum_scores(engagement_timeline)
            
            # Calculate retention scores
            retention_scores = self._calculate_retention_scores(participants)
            
            # Identify engagement drivers and barriers
            engagement_drivers = self._identify_engagement_drivers(participants)
            engagement_barriers = self._identify_engagement_barriers(participants)
            
            engagement_analytics = EngagementAnalytics(
                meeting_id=meeting_id,
                overall_engagement_score=overall_engagement_score,
                engagement_timeline=engagement_timeline,
                peak_engagement_periods=peak_periods,
                low_engagement_periods=low_periods,
                engagement_distribution=engagement_distribution,
                attention_scores=attention_scores,
                energy_levels=energy_levels,
                momentum_scores=momentum_scores,
                retention_scores=retention_scores,
                engagement_drivers=engagement_drivers,
                engagement_barriers=engagement_barriers,
                metadata={
                    'calculation_time': datetime.now(timezone.utc).isoformat(),
                    'engagement_score_range': [min(engagement_scores), max(engagement_scores)] if engagement_scores else [0, 0]
                },
                created_at=datetime.now(timezone.utc)
            )
            
            return engagement_analytics
            
        except Exception as e:
            logger.error(f"Failed to calculate engagement analytics: {e}")
            return None
    
    async def _calculate_sentiment_analytics(self, meeting_data: Dict[str, Any]) -> Optional[SentimentAnalytics]:
        """Calculate sentiment analytics"""
        try:
            meeting_id = meeting_data['meeting_id']
            participants = meeting_data.get('participants', [])
            text_analyses = meeting_data.get('text_analyses', [])
            
            if len(text_analyses) == 0:
                return None
            
            # Calculate overall sentiment score
            sentiment_scores = []
            for analysis in text_analyses:
                sentiment = analysis.get('sentiment', {})
                if 'score' in sentiment:
                    sentiment_scores.append(sentiment['score'])
            
            overall_sentiment_score = np.mean(sentiment_scores) if sentiment_scores else 0
            
            # Generate sentiment timeline
            sentiment_timeline = self._generate_sentiment_timeline(text_analyses)
            
            # Sentiment distribution
            sentiment_distribution = self._calculate_sentiment_distribution(text_analyses)
            
            # Sentiment trends
            sentiment_trends = self._calculate_sentiment_trends(sentiment_timeline)
            
            # Identify sentiment shifts
            sentiment_shifts = self._identify_sentiment_shifts(sentiment_timeline)
            
            # Calculate emotional intensity
            emotional_intensity = self._calculate_emotional_intensity(text_analyses)
            
            # Calculate sentiment volatility
            sentiment_volatility = np.std(sentiment_scores) if len(sentiment_scores) > 1 else 0
            
            # Calculate sentiment correlations
            sentiment_correlations = self._calculate_sentiment_correlations(
                sentiment_scores, participants
            )
            
            # Identify sentiment drivers
            sentiment_drivers = self._identify_sentiment_drivers(text_analyses)
            
            # Extract sentiment topics
            sentiment_topics = self._extract_sentiment_topics(text_analyses)
            
            sentiment_analytics = SentimentAnalytics(
                meeting_id=meeting_id,
                overall_sentiment_score=overall_sentiment_score,
                sentiment_timeline=sentiment_timeline,
                sentiment_distribution=sentiment_distribution,
                sentiment_trends=sentiment_trends,
                sentiment_shifts=sentiment_shifts,
                emotional_intensity=emotional_intensity,
                sentiment_volatility=sentiment_volatility,
                sentiment_correlations=sentiment_correlations,
                sentiment_drivers=sentiment_drivers,
                sentiment_topics=sentiment_topics,
                metadata={
                    'calculation_time': datetime.now(timezone.utc).isoformat(),
                    'sentiment_score_range': [min(sentiment_scores), max(sentiment_scores)] if sentiment_scores else [0, 0],
                    'text_analyses_count': len(text_analyses)
                },
                created_at=datetime.now(timezone.utc)
            )
            
            return sentiment_analytics
            
        except Exception as e:
            logger.error(f"Failed to calculate sentiment analytics: {e}")
            return None
    
    async def _calculate_collaboration_analytics(self, meeting_data: Dict[str, Any]) -> Optional[CollaborationAnalytics]:
        """Calculate collaboration analytics"""
        try:
            meeting_id = meeting_data['meeting_id']
            participants = meeting_data.get('participants', [])
            interactions = meeting_data.get('interactions', [])
            
            if len(participants) < 2:
                return None
            
            # Build interaction network
            interaction_network = self._build_interaction_network(participants, interactions)
            
            # Calculate collaboration index
            collaboration_index = self._calculate_collaboration_index(interaction_network)
            
            # Identify collaboration pairs
            collaboration_pairs = self._identify_collaboration_pairs(interactions)
            
            # Calculate knowledge sharing metrics
            knowledge_sharing_metrics = self._calculate_knowledge_sharing_metrics(
                participants, interactions
            )
            
            # Count ideas generated
            idea_generation_count = self._count_ideas_generated(interactions)
            
            # Calculate decision making speed
            decision_making_speed = self._calculate_decision_making_speed(interactions)
            
            # Calculate consensus reaching time
            consensus_reaching_time = self._calculate_consensus_reaching_time(interactions)
            
            # Calculate conflict resolution metrics
            conflict_resolution_metrics = self._calculate_conflict_resolution_metrics(interactions)
            
            # Calculate cross-functional collaboration
            cross_functional_collaboration = self._calculate_cross_functional_collaboration(participants)
            
            # Calculate collaboration quality score
            collaboration_quality_score = self._calculate_collaboration_quality_score(
                collaboration_index, collaboration_pairs, consensus_reaching_time
            )
            
            collaboration_analytics = CollaborationAnalytics(
                meeting_id=meeting_id,
                collaboration_index=collaboration_index,
                interaction_network=interaction_network,
                collaboration_pairs=collaboration_pairs,
                knowledge_sharing_metrics=knowledge_sharing_metrics,
                idea_generation_count=idea_generation_count,
                decision_making_speed=decision_making_speed,
                consensus_reaching_time=consensus_reaching_time,
                conflict_resolution_metrics=conflict_resolution_metrics,
                cross_functional_collaboration=cross_functional_collaboration,
                collaboration_quality_score=collaboration_quality_score,
                metadata={
                    'calculation_time': datetime.now(timezone.utc).isoformat(),
                    'interaction_count': len(interactions),
                    'participant_count': len(participants)
                },
                created_at=datetime.now(timezone.utc)
            )
            
            return collaboration_analytics
            
        except Exception as e:
            logger.error(f"Failed to calculate collaboration analytics: {e}")
            return None
    
    async def _calculate_productivity_analytics(self, meeting_data: Dict[str, Any]) -> Optional[ProductivityAnalytics]:
        """Calculate productivity analytics"""
        try:
            meeting_id = meeting_data['meeting_id']
            agenda = meeting_data.get('agenda', [])
            action_items = meeting_data.get('action_items', [])
            decisions = meeting_data.get('decisions', [])
            participants = meeting_data.get('participants', [])
            
            if not participants:
                return None
            
            # Calculate productivity score
            productivity_score = self._calculate_productivity_score(
                meeting_data, agenda, action_items, decisions
            )
            
            # Calculate time efficiency
            time_efficiency = self._calculate_time_efficiency(meeting_data)
            
            # Count decisions
            decision_count = len(decisions)
            
            # Count action items
            action_items_count = len(action_items)
            
            # Calculate goal completion rate
            goal_completion_rate = self._calculate_goal_completion_rate(agenda, decisions)
            
            # Calculate agenda adherence
            agenda_adherence = self._calculate_agenda_adherence(meeting_data)
            
            # Calculate time on topic
            time_on_topic = self._calculate_time_on_topic(meeting_data)
            
            # Calculate tangent duration
            tangent_duration = self._calculate_tangent_duration(meeting_data)
            
            # Calculate focus score
            focus_score = self._calculate_focus_score(time_on_topic, tangent_duration)
            
            # Calculate output quality score
            output_quality_score = self._calculate_output_quality_score(decisions, action_items)
            
            # Identify productivity barriers
            productivity_barriers = self._identify_productivity_barriers(meeting_data)
            
            # Identify productivity enablers
            productivity_enablers = self._identify_productivity_enablers(meeting_data)
            
            productivity_analytics = ProductivityAnalytics(
                meeting_id=meeting_id,
                productivity_score=productivity_score,
                time_efficiency=time_efficiency,
                decision_count=decision_count,
                action_items_count=action_items_count,
                goal_completion_rate=goal_completion_rate,
                agenda_adherence=agenda_adherence,
                time_on_topic=time_on_topic,
                tangent_duration=tangent_duration,
                focus_score=focus_score,
                output_quality_score=output_quality_score,
                productivity_barriers=productivity_barriers,
                productivity_enablers=productivity_enablers,
                metadata={
                    'calculation_time': datetime.now(timezone.utc).isoformat(),
                    'meeting_duration_minutes': meeting_data.get('duration_minutes', 0)
                },
                created_at=datetime.now(timezone.utc)
            )
            
            return productivity_analytics
            
        except Exception as e:
            logger.error(f"Failed to calculate productivity analytics: {e}")
            return None
    
    async def _calculate_business_impact_analytics(self, meeting_data: Dict[str, Any]) -> Optional[BusinessImpactAnalytics]:
        """Calculate business impact analytics"""
        try:
            meeting_id = meeting_data['meeting_id']
            participants = meeting_data.get('participants', [])
            meeting_type = meeting_data.get('meeting_type', 'general')
            strategic_goals = meeting_data.get('strategic_goals', [])
            
            # Calculate ROI score
            roi_score = self._calculate_roi_score(meeting_data)
            
            # Perform cost-benefit analysis
            cost_benefit_analysis = self._perform_cost_benefit_analysis(meeting_data)
            
            # Calculate business value generated
            business_value_generated = self._calculate_business_value_generated(meeting_data)
            
            # Calculate strategic alignment
            strategic_alignment = self._calculate_strategic_alignment(strategic_goals, meeting_data)
            
            # Calculate stakeholder satisfaction
            stakeholder_satisfaction = self._calculate_stakeholder_satisfaction(participants)
            
            # Calculate innovation score
            innovation_score = self._calculate_innovation_score(meeting_data)
            
            # Calculate risk mitigation impact
            risk_mitigation_impact = self._calculate_risk_mitigation_impact(meeting_data)
            
            # Calculate market opportunity value
            market_opportunity_value = self._calculate_market_opportunity_value(meeting_data)
            
            # Calculate customer impact
            customer_impact = self._calculate_customer_impact(meeting_data)
            
            # Calculate operational efficiency impact
            operational_efficiency_impact = self._calculate_operational_efficiency_impact(meeting_data)
            
            business_impact_analytics = BusinessImpactAnalytics(
                meeting_id=meeting_id,
                roi_score=roi_score,
                cost_benefit_analysis=cost_benefit_analysis,
                business_value_generated=business_value_generated,
                strategic_alignment=strategic_alignment,
                stakeholder_satisfaction=stakeholder_satisfaction,
                innovation_score=innovation_score,
                risk_mitigation_impact=risk_mitigation_impact,
                market_opportunity_value=market_opportunity_value,
                customer_impact=customer_impact,
                operational_efficiency_impact=operational_efficiency_impact,
                metadata={
                    'calculation_time': datetime.now(timezone.utc).isoformat(),
                    'meeting_type': meeting_type,
                    'participant_count': len(participants)
                },
                created_at=datetime.now(timezone.utc)
            )
            
            return business_impact_analytics
            
        except Exception as e:
            logger.error(f"Failed to calculate business impact analytics: {e}")
            return None
    
    # Utility Methods for Analytics Calculations
    def _generate_participation_heatmap(self, participants: List[Dict[str, Any]]) -> List[List[int]]:
        """Generate participation heatmap"""
        try:
            # Create a simple 10x10 heatmap
            heatmap = [[0 for _ in range(10)] for _ in range(10)]
            
            # Fill based on speaking patterns (simplified)
            for participant in participants:
                speaking_time = participant.get('speaking_time_seconds', 0)
                if speaking_time > 0:
                    # Map to grid (simplified)
                    grid_x = min(9, int(speaking_time / 60))  # Minutes to grid
                    grid_y = min(9, (len(participant.get('name', '')) * 7) % 10)  # Name-based position
                    heatmap[grid_y][grid_x] += 1
            
            return heatmap
            
        except Exception as e:
            logger.error(f"Failed to generate participation heatmap: {e}")
            return [[0 for _ in range(10)] for _ in range(10)]
    
    def _analyze_speaking_patterns(self, participants: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """Analyze speaking patterns"""
        patterns = {}
        
        for participant in participants:
            participant_id = participant['id']
            # Generate simulated speaking pattern (in real implementation, would use actual data)
            pattern = np.random.exponential(scale=30, size=20).tolist()  # 20 segments
            patterns[participant_id] = pattern
        
        return patterns
    
    def _calculate_response_times(self, participants: List[Dict[str, Any]]) -> Dict[str, List[float]]:
        """Calculate response times"""
        response_times = {}
        
        for participant in participants:
            participant_id = participant['id']
            # Generate simulated response times (in real implementation, would analyze actual interactions)
            times = np.random.normal(loc=2.5, scale=1.0, size=10).tolist()  # 10 response times
            times = [max(0.5, t) for t in times]  # Minimum 0.5 seconds
            response_times[participant_id] = times
        
        return response_times
    
    def _extract_question_answer_pairs(self, meeting_data: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Extract question-answer pairs"""
        # Generate simulated pairs (in real implementation, would analyze actual text)
        pairs = [
            {
                'question': 'What are our priorities for Q1?',
                'answer': 'Focus on customer acquisition and product development',
                'asker': 'user_1',
                'answerer': 'user_2',
                'timestamp': '2024-01-15T10:30:00Z'
            },
            {
                'question': 'What is the timeline for the new feature?',
                'answer': 'Target launch is end of February',
                'asker': 'user_3',
                'answerer': 'user_1',
                'timestamp': '2024-01-15T10:45:00Z'
            }
        ]
        
        return pairs
    
    def _generate_engagement_timeline(self, participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate engagement timeline"""
        timeline = []
        
        # Generate 5-minute intervals for 1-hour meeting
        for i in range(12):
            timestamp = f'2024-01-15T10:{i*5:02d}:00Z'
            
            # Calculate engagement for this interval
            interval_engagement = []
            for participant in participants:
                # Simulate engagement with some variation
                base_engagement = participant.get('engagement_score', 0.5)
                variation = np.random.normal(0, 0.1)
                interval_engagement.append(max(0, min(1, base_engagement + variation)))
            
            average_engagement = np.mean(interval_engagement)
            
            timeline.append({
                'timestamp': timestamp,
                'engagement_score': average_engagement,
                'participant_count': len(interval_engagement),
                'high_engagement_participants': sum(1 for e in interval_engagement if e > 0.7),
                'low_engagement_participants': sum(1 for e in interval_engagement if e < 0.3)
            })
        
        return timeline
    
    def _identify_engagement_periods(self, timeline: List[Dict[str, Any]]) -> Tuple[List[Tuple], List[Tuple]]:
        """Identify peak and low engagement periods"""
        peak_periods = []
        low_periods = []
        
        # Simplified identification (in real implementation, would use more sophisticated analysis)
        for i in range(len(timeline) - 2):
            current = timeline[i]['engagement_score']
            next_one = timeline[i + 1]['engagement_score']
            next_two = timeline[i + 2]['engagement_score']
            
            if current > 0.7 and next_one > 0.7 and next_two > 0.7:
                start = timeline[i]['timestamp']
                end = timeline[i + 2]['timestamp']
                peak_periods.append((start, end))
            elif current < 0.3 and next_one < 0.3 and next_two < 0.3:
                start = timeline[i]['timestamp']
                end = timeline[i + 2]['timestamp']
                low_periods.append((start, end))
        
        return peak_periods, low_periods
    
    def _calculate_engagement_distribution(self, engagement_scores: List[float]) -> Dict[EngagementLevel, int]:
        """Calculate engagement distribution"""
        distribution = {
            EngagementLevel.HIGH: 0,
            EngagementLevel.MEDIUM: 0,
            EngagementLevel.LOW: 0,
            EngagementLevel.VERY_LOW: 0
        }
        
        for score in engagement_scores:
            if score >= 0.7:
                distribution[EngagementLevel.HIGH] += 1
            elif score >= 0.5:
                distribution[EngagementLevel.MEDIUM] += 1
            elif score >= 0.3:
                distribution[EngagementLevel.LOW] += 1
            else:
                distribution[EngagementLevel.VERY_LOW] += 1
        
        return distribution
    
    def _calculate_attention_scores(self, participants: List[Dict[str, Any]]) -> List[float]:
        """Calculate attention scores over time"""
        # Generate simulated attention scores (in real implementation, would use actual data)
        scores = []
        for _ in range(60):  # 60 data points for 1 hour
            score = np.random.beta(2, 2)  # Beta distribution for attention
            scores.append(score)
        
        return scores
    
    def _calculate_energy_levels(self, participants: List[Dict[str, Any]]) -> List[float]:
        """Calculate energy levels over time"""
        # Generate simulated energy levels
        levels = []
        current_energy = 0.5
        
        for _ in range(60):  # 60 data points
            # Random walk with mean reversion
            change = np.random.normal(0, 0.1)
            current_energy = 0.5 + (current_energy - 0.5) * 0.9 + change
            current_energy = max(0, min(1, current_energy))
            levels.append(current_energy)
        
        return levels
    
    def _calculate_momentum_scores(self, timeline: List[Dict[str, Any]]) -> List[float]:
        """Calculate momentum scores"""
        if not timeline:
            return []
        
        engagement_scores = [point['engagement_score'] for point in timeline]
        
        # Calculate momentum as rate of change
        momentum_scores = []
        for i in range(len(engagement_scores)):
            if i == 0:
                momentum_scores.append(0)
            else:
                change = engagement_scores[i] - engagement_scores[i-1]
                momentum_scores.append(change)
        
        return momentum_scores
    
    def _calculate_retention_scores(self, participants: List[Dict[str, Any]]) -> List[float]:
        """Calculate retention scores over time"""
        # Generate simulated retention scores (information retention)
        scores = []
        for _ in range(60):  # 60 data points
            score = 0.8 + 0.2 * np.cos(2 * np.pi * _ / 20)  # Periodic variation
            scores.append(score)
        
        return scores
    
    def _identify_engagement_drivers(self, participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify engagement drivers"""
        drivers = [
            {
                'driver': 'Interactive discussion',
                'impact': 0.8,
                'description': 'High engagement during interactive discussions'
            },
            {
                'driver': 'Visual content',
                'impact': 0.6,
                'description': 'Engagement increases with visual presentations'
            },
            {
                'driver': 'Breakout sessions',
                'impact': 0.7,
                'description': 'Smaller groups drive higher participation'
            }
        ]
        
        return drivers
    
    def _identify_engagement_barriers(self, participants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify engagement barriers"""
        barriers = [
            {
                'barrier': 'Long monologues',
                'impact': -0.6,
                'description': 'Engagement drops during long speeches'
            },
            {
                'barrier': 'Technical issues',
                'impact': -0.8,
                'description': 'Audio/video problems significantly reduce engagement'
            },
            {
                'barrier': 'Off-topic discussions',
                'impact': -0.5,
                'description': 'Focus loss when conversation drifts from agenda'
            }
        ]
        
        return barriers
    
    def _generate_sentiment_timeline(self, text_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Generate sentiment timeline"""
        timeline = []
        
        for analysis in text_analyses:
            sentiment = analysis.get('sentiment', {})
            score = sentiment.get('score', 0)
            label = sentiment.get('sentiment', 'neutral')
            
            timeline.append({
                'timestamp': analysis.get('timestamp'),
                'sentiment_score': score,
                'sentiment_label': label,
                'confidence': sentiment.get('confidence', 0.5),
                'text_length': len(analysis.get('text', '')),
                'participant_id': analysis.get('participant_id')
            })
        
        return timeline
    
    def _calculate_sentiment_distribution(self, text_analyses: List[Dict[str, Any]]) -> Dict[SentimentLabel, int]:
        """Calculate sentiment distribution"""
        distribution = {
            SentimentLabel.POSITIVE: 0,
            SentimentLabel.NEUTRAL: 0,
            SentimentLabel.NEGATIVE: 0,
            SentimentLabel.MIXED: 0
        }
        
        for analysis in text_analyses:
            sentiment = analysis.get('sentiment', {})
            label = sentiment.get('sentiment', 'neutral')
            
            if label == 'positive':
                distribution[SentimentLabel.POSITIVE] += 1
            elif label == 'negative':
                distribution[SentimentLabel.NEGATIVE] += 1
            elif label == 'mixed':
                distribution[SentimentLabel.MIXED] += 1
            else:
                distribution[SentimentLabel.NEUTRAL] += 1
        
        return distribution
    
    def _calculate_sentiment_trends(self, timeline: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate sentiment trends"""
        if not timeline:
            return {}
        
        # Calculate trend over time
        sentiment_scores = [point['sentiment_score'] for point in timeline]
        
        # Simple linear trend
        if len(sentiment_scores) < 2:
            return {}
        
        x = np.arange(len(sentiment_scores))
        slope, intercept, r_value, p_value, std_err = stats.linregress(x, sentiment_scores)
        
        trends = {
            'linear_trend': slope,
            'trend_strength': abs(r_value),
            'volatility': np.std(sentiment_scores),
            'average_sentiment': np.mean(sentiment_scores),
            'sentiment_range': np.max(sentiment_scores) - np.min(sentiment_scores)
        }
        
        return trends
    
    def _identify_sentiment_shifts(self, timeline: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify significant sentiment shifts"""
        shifts = []
        
        if len(timeline) < 2:
            return shifts
        
        # Find shifts where sentiment changes significantly
        for i in range(1, len(timeline)):
            prev_sentiment = timeline[i-1]['sentiment_score']
            curr_sentiment = timeline[i]['sentiment_score']
            
            # Define significant shift
            shift_threshold = 0.5
            
            if abs(curr_sentiment - prev_sentiment) >= shift_threshold:
                shifts.append({
                    'timestamp': timeline[i]['timestamp'],
                    'previous_sentiment': prev_sentiment,
                    'current_sentiment': curr_sentiment,
                    'shift_magnitude': curr_sentiment - prev_sentiment,
                    'shift_type': 'positive' if curr_sentiment > prev_sentiment else 'negative',
                    'context': timeline[i].get('text', '')[:100] + '...'  # First 100 chars
                })
        
        return shifts
    
    def _calculate_emotional_intensity(self, text_analyses: List[Dict[str, Any]]) -> List[float]:
        """Calculate emotional intensity over time"""
        intensities = []
        
        for analysis in text_analyses:
            emotions = analysis.get('emotions', {})
            # Calculate intensity as sum of absolute emotion values
            intensity = sum(abs(val) for val in emotions.values())
            intensities.append(intensity)
        
        return intensities
    
    def _calculate_sentiment_correlations(self, sentiment_scores: List[float], 
                                      participants: List[Dict[str, Any]]) -> Dict[str, float]:
        """Calculate sentiment correlations with other metrics"""
        correlations = {}
        
        # Correlate sentiment with speaking time
        speaking_times = [p.get('speaking_time_seconds', 0) for p in participants]
        if len(speaking_times) > 1 and len(sentiment_scores) > 1:
            correlation = np.corrcoef(speaking_times, sentiment_scores)[0, 1]
            if not np.isnan(correlation):
                correlations['speaking_time'] = correlation
        
        # Correlate sentiment with engagement
        engagement_scores = [p.get('engagement_score', 0) for p in participants]
        if len(engagement_scores) > 1 and len(sentiment_scores) > 1:
            correlation = np.corrcoef(engagement_scores, sentiment_scores)[0, 1]
            if not np.isnan(correlation):
                correlations['engagement_score'] = correlation
        
        return correlations
    
    def _identify_sentiment_drivers(self, text_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Identify sentiment drivers"""
        # Analyze topics associated with positive/negative sentiment
        positive_topics = []
        negative_topics = []
        
        for analysis in text_analyses:
            sentiment = analysis.get('sentiment', {})
            score = sentiment.get('score', 0)
            topics = analysis.get('topics', [])
            
            if score > 0.5:
                positive_topics.extend(topics)
            elif score < -0.5:
                negative_topics.extend(topics)
        
        drivers = []
        
        # Analyze topic frequency
        from collections import Counter
        
        positive_counter = Counter(positive_topics)
        negative_counter = Counter(negative_topics)
        
        # Top positive drivers
        for topic, count in positive_counter.most_common(3):
            drivers.append({
                'driver': topic,
                'sentiment': 'positive',
                'impact_score': count / len(text_analyses),
                'description': f'Topic "{topic}" frequently associated with positive sentiment'
            })
        
        # Top negative drivers
        for topic, count in negative_counter.most_common(3):
            drivers.append({
                'driver': topic,
                'sentiment': 'negative',
                'impact_score': count / len(text_analyses),
                'description': f'Topic "{topic}" frequently associated with negative sentiment'
            })
        
        return drivers
    
    def _extract_sentiment_topics(self, text_analyses: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Extract topics with sentiment information"""
        topic_sentiments = {}
        
        for analysis in text_analyses:
            sentiment = analysis.get('sentiment', {})
            score = sentiment.get('score', 0)
            topics = analysis.get('topics', [])
            
            for topic in topics:
                if topic not in topic_sentiments:
                    topic_sentiments[topic] = {
                        'positive_count': 0,
                        'negative_count': 0,
                        'neutral_count': 0,
                        'total_score': 0,
                        'mentions': 0
                    }
                
                if score > 0.2:
                    topic_sentiments[topic]['positive_count'] += 1
                elif score < -0.2:
                    topic_sentiments[topic]['negative_count'] += 1
                else:
                    topic_sentiments[topic]['neutral_count'] += 1
                
                topic_sentiments[topic]['total_score'] += score
                topic_sentiments[topic]['mentions'] += 1
        
        # Convert to list and calculate sentiment score
        topics_with_sentiment = []
        
        for topic, data in topic_sentiments.items():
            if data['mentions'] >= 2:  # Only include topics mentioned multiple times
                avg_sentiment = data['total_score'] / data['mentions']
                
                topics_with_sentiment.append({
                    'topic': topic,
                    'sentiment_score': avg_sentiment,
                    'positive_count': data['positive_count'],
                    'negative_count': data['negative_count'],
                    'neutral_count': data['neutral_count'],
                    'total_mentions': data['mentions'],
                    'sentiment_label': 'positive' if avg_sentiment > 0.2 else 'negative' if avg_sentiment < -0.2 else 'neutral'
                })
        
        # Sort by mention count
        topics_with_sentiment.sort(key=lambda x: x['total_mentions'], reverse=True)
        
        return topics_with_sentiment
    
    # Database Storage Methods
    async def _store_analytics(self, meeting_id: str, analytics_results: Dict[str, Any]) -> None:
        """Store analytics in database"""
        if not self.db_pool:
            return
        
        try:
            async with self.db_pool.acquire() as conn:
                # Store participation analytics
                if 'participation' in analytics_results:
                    await self._store_participation_analytics(conn, analytics_results['participation'])
                
                # Store engagement analytics
                if 'engagement' in analytics_results:
                    await self._store_engagement_analytics(conn, analytics_results['engagement'])
                
                # Store sentiment analytics
                if 'sentiment' in analytics_results:
                    await self._store_sentiment_analytics(conn, analytics_results['sentiment'])
                
                # Store collaboration analytics
                if 'collaboration' in analytics_results:
                    await self._store_collaboration_analytics(conn, analytics_results['collaboration'])
                
                # Store productivity analytics
                if 'productivity' in analytics_results:
                    await self._store_productivity_analytics(conn, analytics_results['productivity'])
                
                # Store business impact analytics
                if 'business_impact' in analytics_results:
                    await self._store_business_impact_analytics(conn, analytics_results['business_impact'])
                
                logger.info(f"Stored analytics for meeting {meeting_id}")
                
        except Exception as e:
            logger.error(f"Failed to store analytics for meeting {meeting_id}: {e}")
    
    async def _store_participation_analytics(self, conn, data: Dict[str, Any]) -> None:
        """Store participation analytics"""
        await conn.execute("""
            INSERT INTO zoom_participation_analytics (
                meeting_id, total_participants, speaking_participants, silent_participants,
                average_participation_rate, participation_distribution, speaking_time_distribution,
                interaction_frequency, participation_heatmap, speaking_patterns, response_times,
                question_answer_pairs, metadata, created_at
            ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14)
            ON CONFLICT (meeting_id) DO UPDATE SET
                total_participants = EXCLUDED.total_participants,
                speaking_participants = EXCLUDED.speaking_participants,
                silent_participants = EXCLUDED.silent_participants,
                average_participation_rate = EXCLUDED.average_participation_rate,
                participation_distribution = EXCLUDED.participation_distribution,
                speaking_time_distribution = EXCLUDED.speaking_time_distribution,
                interaction_frequency = EXCLUDED.interaction_frequency,
                participation_heatmap = EXCLUDED.participation_heatmap,
                speaking_patterns = EXCLUDED.speaking_patterns,
                response_times = EXCLUDED.response_times,
                question_answer_pairs = EXCLUDED.question_answer_pairs,
                metadata = EXCLUDED.metadata
        """,
        data['meeting_id'], data['total_participants'], data['speaking_participants'],
        data['silent_participants'], data['average_participation_rate'],
        json.dumps(data['participation_distribution']), json.dumps(data['speaking_time_distribution']),
        json.dumps(data['interaction_frequency']), json.dumps(data['participation_heatmap']),
        json.dumps(data['speaking_patterns']), json.dumps(data['response_times']),
        json.dumps(data['question_answer_pairs']), json.dumps(data['metadata']),
        datetime.now(timezone.utc)
        )
    
    # Performance Metrics
    def _update_average_processing_time(self, processing_time: float) -> None:
        """Update average processing time"""
        total_analytics = self.performance_metrics['analytics_calculated']
        
        if total_analytics > 0:
            self.performance_metrics['average_processing_time'] = (
                (self.performance_metrics['average_processing_time'] * (total_analytics - 1) + processing_time) /
                total_analytics
            )
    
    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        return self.performance_metrics.copy()
    
    def get_meeting_analytics(self, meeting_id: str) -> Dict[str, Any]:
        """Get all analytics for a specific meeting"""
        analytics = {}
        
        if meeting_id in self.participation_analytics:
            analytics['participation'] = asdict(self.participation_analytics[meeting_id])
        
        if meeting_id in self.engagement_analytics:
            analytics['engagement'] = asdict(self.engagement_analytics[meeting_id])
        
        if meeting_id in self.sentiment_analytics:
            analytics['sentiment'] = asdict(self.sentiment_analytics[meeting_id])
        
        if meeting_id in self.collaboration_analytics:
            analytics['collaboration'] = asdict(self.collaboration_analytics[meeting_id])
        
        if meeting_id in self.productivity_analytics:
            analytics['productivity'] = asdict(self.productivity_analytics[meeting_id])
        
        if meeting_id in self.business_impact_analytics:
            analytics['business_impact'] = asdict(self.business_impact_analytics[meeting_id])
        
        return analytics