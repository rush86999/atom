"""
ATOM Slack Analytics Engine
Comprehensive analytics with reporting, insights, and predictions
"""

import os
import json
import logging
import asyncio
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import re

logger = logging.getLogger(__name__)

class AnalyticsTimeRange(Enum):
    """Analytics time ranges"""
    TODAY = "today"
    YESTERDAY = "yesterday"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    CUSTOM = "custom"

class AnalyticsMetric(Enum):
    """Analytics metrics"""
    MESSAGE_VOLUME = "message_volume"
    USER_ACTIVITY = "user_activity"
    ENGAGEMENT = "engagement"
    RESPONSE_TIME = "response_time"
    SENTIMENT = "sentiment"
    COLLABORATION = "collaboration"
    PRODUCTIVITY = "productivity"
    TOPICS = "topics"
    REACTIONS = "reactions"
    FILE_SHARING = "file_sharing"

class AnalyticsGranularity(Enum):
    """Analytics granularity levels"""
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"

@dataclass
class AnalyticsDataPoint:
    """Single analytics data point"""
    timestamp: datetime
    metric: AnalyticsMetric
    value: Union[int, float, str]
    dimensions: Dict[str, Any] = None
    metadata: Dict[str, Any] = None
    
    def __post_init__(self):
        if self.dimensions is None:
            self.dimensions = {}
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp.tzinfo is None:
            self.timestamp = self.timestamp.replace(tzinfo=timezone.utc)

@dataclass
class AnalyticsReport:
    """Analytics report configuration"""
    id: str
    name: str
    description: str
    metrics: List[AnalyticsMetric]
    time_range: AnalyticsTimeRange
    granularity: AnalyticsGranularity
    filters: Dict[str, Any] = None
    visualizations: List[str] = None
    created_by: str
    created_at: datetime = None
    is_scheduled: bool = False
    schedule_cron: Optional[str] = None
    recipients: List[str] = None
    
    def __post_init__(self):
        if self.filters is None:
            self.filters = {}
        if self.visualizations is None:
            self.visualizations = []
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.recipients is None:
            self.recipients = []

class SlackAnalyticsEngine:
    """Slack analytics engine with comprehensive reporting and insights"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.database = config.get('database')
        self.redis_client = config.get('redis_client')
        
        # Cache for computed analytics
        self.analytics_cache: Dict[str, Any] = {}
        self.cache_ttl = config.get('cache_ttl', 300)  # 5 minutes
        
        # Sentiment analysis (placeholder)
        self.sentiment_analyzer = config.get('sentiment_analyzer')
        
        # Machine learning models (placeholder)
        self.prediction_models = config.get('prediction_models', {})
        
        # Report configurations
        self.reports: Dict[str, AnalyticsReport] = {}
        
        # Analytics processors
        self.processors = {
            AnalyticsMetric.MESSAGE_VOLUME: self._process_message_volume,
            AnalyticsMetric.USER_ACTIVITY: self._process_user_activity,
            AnalyticsMetric.ENGAGEMENT: self._process_engagement,
            AnalyticsMetric.RESPONSE_TIME: self._process_response_time,
            AnalyticsMetric.SENTIMENT: self._process_sentiment,
            AnalyticsMetric.COLLABORATION: self._process_collaboration,
            AnalyticsMetric.PRODUCTIVITY: self._process_productivity,
            AnalyticsMetric.TOPICS: self._process_topics,
            AnalyticsMetric.REACTIONS: self._process_reactions,
            AnalyticsMetric.FILE_SHARING: self._process_file_sharing
        }
        
        logger.info("Slack Analytics Engine initialized")
    
    async def get_analytics(self, metric: AnalyticsMetric, 
                          time_range: AnalyticsTimeRange,
                          granularity: AnalyticsGranularity = AnalyticsGranularity.HOUR,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None,
                          channel_ids: List[str] = None,
                          user_ids: List[str] = None) -> List[AnalyticsDataPoint]:
        """Get analytics data for specific metric"""
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                metric, time_range, granularity, filters, workspace_id, channel_ids, user_ids
            )
            
            # Check cache
            cached_data = self._get_cached_analytics(cache_key)
            if cached_data:
                return cached_data
            
            # Get data from database
            raw_data = await self._fetch_data(
                metric, time_range, filters, workspace_id, channel_ids, user_ids
            )
            
            # Process data
            processor = self.processors.get(metric)
            if not processor:
                raise ValueError(f"No processor found for metric: {metric}")
            
            processed_data = await processor(raw_data, granularity)
            
            # Cache results
            self._cache_analytics(cache_key, processed_data)
            
            return processed_data
            
        except Exception as e:
            logger.error(f"Error getting analytics for {metric}: {e}")
            return []
    
    async def get_insights(self, metric: AnalyticsMetric, 
                          time_range: AnalyticsTimeRange,
                          filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get insights for specific metric"""
        try:
            # Get analytics data
            data = await self.get_analytics(metric, time_range, AnalyticsGranularity.DAY, filters)
            
            if not data:
                return {}
            
            # Generate insights based on metric type
            insights = {
                'metric': metric.value,
                'time_range': time_range.value,
                'generated_at': datetime.utcnow().isoformat(),
                'data_points': len(data)
            }
            
            if metric == AnalyticsMetric.MESSAGE_VOLUME:
                insights.update(await self._get_message_volume_insights(data))
            elif metric == AnalyticsMetric.USER_ACTIVITY:
                insights.update(await self._get_user_activity_insights(data))
            elif metric == AnalyticsMetric.ENGAGEMENT:
                insights.update(await self._get_engagement_insights(data))
            elif metric == AnalyticsMetric.RESPONSE_TIME:
                insights.update(await self._get_response_time_insights(data))
            elif metric == AnalyticsMetric.SENTIMENT:
                insights.update(await self._get_sentiment_insights(data))
            
            return insights
            
        except Exception as e:
            logger.error(f"Error getting insights for {metric}: {e}")
            return {}
    
    async def generate_report(self, report_id: str) -> Dict[str, Any]:
        """Generate analytics report"""
        try:
            report = self.reports.get(report_id)
            if not report:
                raise ValueError(f"Report not found: {report_id}")
            
            report_data = {
                'id': report.id,
                'name': report.name,
                'description': report.description,
                'generated_at': datetime.utcnow().isoformat(),
                'time_range': report.time_range.value,
                'granularity': report.granularity.value,
                'metrics': []
            }
            
            # Generate data for each metric
            for metric in report.metrics:
                try:
                    metric_data = await self.get_analytics(
                        metric, 
                        report.time_range,
                        report.granularity,
                        report.filters
                    )
                    
                    metric_insights = await self.get_insights(
                        metric, 
                        report.time_range,
                        report.filters
                    )
                    
                    report_data['metrics'].append({
                        'name': metric.value,
                        'data': [asdict(point) for point in metric_data],
                        'insights': metric_insights
                    })
                    
                except Exception as e:
                    logger.error(f"Error generating data for metric {metric}: {e}")
                    report_data['metrics'].append({
                        'name': metric.value,
                        'error': str(e)
                    })
            
            # Add visualizations
            report_data['visualizations'] = report.visualizations
            
            return report_data
            
        except Exception as e:
            logger.error(f"Error generating report {report_id}: {e}")
            return {'error': str(e)}
    
    async def get_top_users(self, metric: AnalyticsMetric, 
                          time_range: AnalyticsTimeRange,
                          limit: int = 10,
                          filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get top users by specific metric"""
        try:
            data = await self.get_analytics(metric, time_range, AnalyticsGranularity.DAY, filters)
            
            # Aggregate data by user
            user_stats = defaultdict(lambda: {'total': 0, 'count': 0})
            
            for point in data:
                user_id = point.dimensions.get('user_id')
                if user_id:
                    user_stats[user_id]['total'] += point.value
                    user_stats[user_id]['count'] += 1
            
            # Sort and return top users
            top_users = []
            for user_id, stats in user_stats.items():
                top_users.append({
                    'user_id': user_id,
                    'total_value': stats['total'],
                    'data_points': stats['count'],
                    'average_value': stats['total'] / stats['count']
                })
            
            top_users.sort(key=lambda x: x['total_value'], reverse=True)
            return top_users[:limit]
            
        except Exception as e:
            logger.error(f"Error getting top users: {e}")
            return []
    
    async def get_top_channels(self, metric: AnalyticsMetric,
                             time_range: AnalyticsTimeRange,
                             limit: int = 10,
                             filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get top channels by specific metric"""
        try:
            data = await self.get_analytics(metric, time_range, AnalyticsGranularity.DAY, filters)
            
            # Aggregate data by channel
            channel_stats = defaultdict(lambda: {'total': 0, 'count': 0})
            
            for point in data:
                channel_id = point.dimensions.get('channel_id')
                if channel_id:
                    channel_stats[channel_id]['total'] += point.value
                    channel_stats[channel_id]['count'] += 1
            
            # Sort and return top channels
            top_channels = []
            for channel_id, stats in channel_stats.items():
                top_channels.append({
                    'channel_id': channel_id,
                    'total_value': stats['total'],
                    'data_points': stats['count'],
                    'average_value': stats['total'] / stats['count']
                })
            
            top_channels.sort(key=lambda x: x['total_value'], reverse=True)
            return top_channels[:limit]
            
        except Exception as e:
            logger.error(f"Error getting top channels: {e}")
            return []
    
    async def get_trending_topics(self, time_range: AnalyticsTimeRange,
                                limit: int = 20,
                                filters: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Get trending topics and keywords"""
        try:
            data = await self.get_analytics(AnalyticsMetric.TOPICS, time_range, AnalyticsGranularity.DAY, filters)
            
            # Aggregate topics
            topic_counts = Counter()
            
            for point in data:
                if isinstance(point.value, list):
                    topic_counts.update(point.value)
                elif isinstance(point.value, str):
                    # Split string into topics
                    topics = [t.strip() for t in point.value.split(',')]
                    topic_counts.update(topics)
            
            # Return top topics
            trending_topics = [
                {'topic': topic, 'mentions': count}
                for topic, count in topic_counts.most_common(limit)
            ]
            
            return trending_topics
            
        except Exception as e:
            logger.error(f"Error getting trending topics: {e}")
            return []
    
    async def get_engagement_heatmap(self, time_range: AnalyticsTimeRange,
                                   filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get engagement heatmap by day of week and hour"""
        try:
            data = await self.get_analytics(
                AnalyticsMetric.ENGAGEMENT, 
                time_range, 
                AnalyticsGranularity.HOUR,
                filters
            )
            
            # Create heatmap data structure
            heatmap = defaultdict(lambda: defaultdict(float))
            
            for point in data:
                timestamp = point.timestamp
                day_of_week = timestamp.strftime('%A')
                hour = timestamp.hour
                
                heatmap[day_of_week][hour] += float(point.value)
            
            # Normalize and format for frontend
            heatmap_data = []
            days = ['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday']
            
            for day in days:
                day_data = {'day': day, 'hours': []}
                
                for hour in range(24):
                    value = heatmap[day][hour]
                    day_data['hours'].append({
                        'hour': hour,
                        'value': value,
                        'normalized': min(value / max(heatmap[day].values()) if heatmap[day].values() else 1, 1)
                    })
                
                heatmap_data.append(day_data)
            
            return {
                'heatmap': heatmap_data,
                'time_range': time_range.value,
                'max_value': max(max(day.values()) for day in heatmap.values()) if heatmap.values() else 0
            }
            
        except Exception as e:
            logger.error(f"Error generating engagement heatmap: {e}")
            return {}
    
    async def predict_message_volume(self, hours_ahead: int = 24,
                                   workspace_id: str = None) -> Dict[str, Any]:
        """Predict message volume for next hours"""
        try:
            # Get historical data for the last 7 days
            historical_data = await self.get_analytics(
                AnalyticsMetric.MESSAGE_VOLUME,
                AnalyticsTimeRange.LAST_7_DAYS,
                AnalyticsGranularity.HOUR,
                {'workspace_id': workspace_id}
            )
            
            if len(historical_data) < 168:  # Need at least 1 week of hourly data
                return {'error': 'Insufficient historical data for prediction'}
            
            # Create time series data
            df = pd.DataFrame([{
                'timestamp': point.timestamp,
                'value': float(point.value)
            } for point in historical_data])
            
            df = df.set_index('timestamp')
            
            # Simple prediction using moving average and seasonality
            predictions = []
            
            for hour in range(hours_ahead):
                # Get same hour from previous days
                same_hour_data = df[df.index.hour == hour]['value']
                
                if len(same_hour_data) >= 3:
                    # Use moving average of last 3 same hours
                    predicted_value = same_hour_data.tail(3).mean()
                else:
                    # Use overall average
                    predicted_value = df['value'].mean()
                
                prediction_time = datetime.utcnow() + timedelta(hours=hour+1)
                predictions.append({
                    'timestamp': prediction_time.isoformat(),
                    'predicted_value': predicted_value,
                    'confidence': 0.7  # Placeholder confidence score
                })
            
            return {
                'predictions': predictions,
                'model_used': 'moving_average_seasonality',
                'confidence_score': 0.7,
                'data_points_used': len(historical_data),
                'prediction_hours': hours_ahead
            }
            
        except Exception as e:
            logger.error(f"Error predicting message volume: {e}")
            return {'error': str(e)}
    
    async def get_productivity_metrics(self, time_range: AnalyticsTimeRange,
                                    filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Get productivity metrics and insights"""
        try:
            # Get multiple metrics
            message_volume = await self.get_analytics(
                AnalyticsMetric.MESSAGE_VOLUME, time_range, AnalyticsGranularity.DAY, filters
            )
            response_time = await self.get_analytics(
                AnalyticsMetric.RESPONSE_TIME, time_range, AnalyticsGranularity.DAY, filters
            )
            collaboration = await self.get_analytics(
                AnalyticsMetric.COLLABORATION, time_range, AnalyticsGranularity.DAY, filters
            )
            
            # Calculate productivity score
            productivity_metrics = {
                'message_volume_score': self._calculate_score(message_volume),
                'response_time_score': self._calculate_score(response_time, reverse=True),
                'collaboration_score': self._calculate_score(collaboration),
                'overall_productivity': 0
            }
            
            # Calculate overall productivity
            productivity_metrics['overall_productivity'] = (
                productivity_metrics['message_volume_score'] * 0.3 +
                productivity_metrics['response_time_score'] * 0.4 +
                productivity_metrics['collaboration_score'] * 0.3
            )
            
            # Add trends
            productivity_metrics['trends'] = self._calculate_trends([
                ('message_volume', message_volume),
                ('response_time', response_time),
                ('collaboration', collaboration)
            ])
            
            return productivity_metrics
            
        except Exception as e:
            logger.error(f"Error getting productivity metrics: {e}")
            return {}
    
    # Data processors
    async def _process_message_volume(self, raw_data: List[Dict], 
                                   granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process message volume data"""
        processed = []
        
        # Group by granularity
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.MESSAGE_VOLUME,
                value=len(group),
                dimensions={
                    'workspace_id': group[0].get('workspace_id'),
                    'channel_id': group[0].get('channel_id')
                }
            ))
        
        return processed
    
    async def _process_user_activity(self, raw_data: List[Dict],
                                   granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process user activity data"""
        processed = []
        
        # Group by user and time
        user_activity = defaultdict(lambda: defaultdict(list))
        
        for item in raw_data:
            user_id = item.get('user_id')
            timestamp = self._parse_timestamp(item.get('timestamp'))
            if user_id and timestamp:
                if granularity == AnalyticsGranularity.HOUR:
                    time_key = timestamp.replace(minute=0, second=0, microsecond=0)
                elif granularity == AnalyticsGranularity.DAY:
                    time_key = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                else:
                    time_key = timestamp
                
                user_activity[user_id][time_key].append(item)
        
        # Process each user's activity
        for user_id, user_times in user_activity.items():
            for timestamp, items in user_times.items():
                active_minutes = len(set(
                    item['timestamp'].replace(second=0, microsecond=0)
                    for item in items
                ))
                
                processed.append(AnalyticsDataPoint(
                    timestamp=timestamp,
                    metric=AnalyticsMetric.USER_ACTIVITY,
                    value=active_minutes,
                    dimensions={
                        'user_id': user_id,
                        'activity_type': 'active_minutes'
                    }
                ))
        
        return processed
    
    async def _process_engagement(self, raw_data: List[Dict],
                                granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process engagement data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            # Calculate engagement score
            total_reactions = sum(len(item.get('reactions', [])) for item in group)
            total_replies = sum(item.get('reply_count', 0) for item in group)
            total_mentions = sum(len(item.get('mentions', [])) for item in group)
            
            engagement_score = (total_reactions * 1 + total_replies * 2 + total_mentions * 3)
            
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.ENGAGEMENT,
                value=engagement_score,
                dimensions={
                    'total_reactions': total_reactions,
                    'total_replies': total_replies,
                    'total_mentions': total_mentions
                }
            ))
        
        return processed
    
    async def _process_response_time(self, raw_data: List[Dict],
                                   granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process response time data"""
        processed = []
        
        # Group by time and calculate average response time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            response_times = []
            
            for item in group:
                if item.get('response_time_seconds'):
                    response_times.append(item['response_time_seconds'])
            
            if response_times:
                avg_response_time = statistics.mean(response_times)
                processed.append(AnalyticsDataPoint(
                    timestamp=timestamp,
                    metric=AnalyticsMetric.RESPONSE_TIME,
                    value=avg_response_time,
                    dimensions={
                        'total_responses': len(response_times),
                        'min_response_time': min(response_times),
                        'max_response_time': max(response_times)
                    }
                ))
        
        return processed
    
    async def _process_sentiment(self, raw_data: List[Dict],
                                granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process sentiment data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            # Analyze sentiment (placeholder)
            sentiments = []
            for item in group:
                text = item.get('text', '')
                if text:
                    # Simple sentiment analysis (placeholder)
                    sentiment_score = self._analyze_sentiment(text)
                    sentiments.append(sentiment_score)
            
            if sentiments:
                avg_sentiment = statistics.mean(sentiments)
                processed.append(AnalyticsDataPoint(
                    timestamp=timestamp,
                    metric=AnalyticsMetric.SENTIMENT,
                    value=avg_sentiment,
                    dimensions={
                        'sentiment_distribution': self._get_sentiment_distribution(sentiments),
                        'total_messages': len(sentiments)
                    }
                ))
        
        return processed
    
    async def _process_collaboration(self, raw_data: List[Dict],
                                   granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process collaboration data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            # Calculate collaboration metrics
            total_threads = sum(1 for item in group if item.get('thread_ts'))
            total_shared_files = sum(len(item.get('files', [])) for item in group)
            total_mentioned_users = sum(len(item.get('mentions', [])) for item in group)
            
            collaboration_score = (total_threads * 2 + total_shared_files * 1 + total_mentioned_users * 1.5)
            
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.COLLABORATION,
                value=collaboration_score,
                dimensions={
                    'total_threads': total_threads,
                    'total_shared_files': total_shared_files,
                    'total_mentioned_users': total_mentioned_users
                }
            ))
        
        return processed
    
    async def _process_productivity(self, raw_data: List[Dict],
                                  granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process productivity data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            # Calculate productivity metrics
            completed_tasks = sum(1 for item in group if 'task' in item.get('text', '').lower())
            decisions_made = sum(1 for item in group if any(
                keyword in item.get('text', '').lower() 
                for keyword in ['decision', 'decided', 'agreed']
            ))
            
            productivity_score = (completed_tasks * 3 + decisions_made * 5)
            
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.PRODUCTIVITY,
                value=productivity_score,
                dimensions={
                    'completed_tasks': completed_tasks,
                    'decisions_made': decisions_made
                }
            ))
        
        return processed
    
    async def _process_topics(self, raw_data: List[Dict],
                            granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process topics data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped.items():
            # Extract topics
            all_topics = []
            for item in group:
                text = item.get('text', '')
                topics = self._extract_topics(text)
                all_topics.extend(topics)
            
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.TOPICS,
                value=list(set(all_topics)),  # Unique topics
                dimensions={
                    'total_topics': len(set(all_topics)),
                    'topic_frequency': dict(Counter(all_topics))
                }
            ))
        
        return processed
    
    async def _process_reactions(self, raw_data: List[Dict],
                               granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process reactions data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped:
            # Count reactions
            reaction_counts = Counter()
            
            for item in group:
                for reaction in item.get('reactions', []):
                    reaction_counts[reaction['name']] += reaction['count']
            
            total_reactions = sum(reaction_counts.values())
            
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.REACTIONS,
                value=total_reactions,
                dimensions={
                    'reaction_breakdown': dict(reaction_counts),
                    'unique_reactions': len(reaction_counts)
                }
            ))
        
        return processed
    
    async def _process_file_sharing(self, raw_data: List[Dict],
                                   granularity: AnalyticsGranularity) -> List[AnalyticsDataPoint]:
        """Process file sharing data"""
        processed = []
        
        # Group by time
        if granularity == AnalyticsGranularity.HOUR:
            grouped = self._group_by_hour(raw_data, 'timestamp')
        elif granularity == AnalyticsGranularity.DAY:
            grouped = self._group_by_day(raw_data, 'timestamp')
        else:
            grouped = self._group_by_raw_timestamp(raw_data)
        
        for timestamp, group in grouped:
            # Count files
            file_counts = Counter()
            total_file_size = 0
            
            for item in group:
                files = item.get('files', [])
                for file in files:
                    file_type = file.get('filetype', 'unknown')
                    file_counts[file_type] += 1
                    total_file_size += file.get('size', 0)
            
            total_files = sum(file_counts.values())
            
            processed.append(AnalyticsDataPoint(
                timestamp=timestamp,
                metric=AnalyticsMetric.FILE_SHARING,
                value=total_files,
                dimensions={
                    'file_type_breakdown': dict(file_counts),
                    'total_file_size': total_file_size,
                    'average_file_size': total_file_size / total_files if total_files > 0 else 0
                }
            ))
        
        return processed
    
    # Helper methods
    def _generate_cache_key(self, metric: AnalyticsMetric, time_range: AnalyticsTimeRange,
                           granularity: AnalyticsGranularity, filters: Dict[str, Any],
                           workspace_id: str, channel_ids: List[str], user_ids: List[str]) -> str:
        """Generate cache key for analytics"""
        key_parts = [
            metric.value,
            time_range.value,
            granularity.value,
            json.dumps(filters or {}, sort_keys=True),
            workspace_id or '',
            ','.join(sorted(channel_ids or [])),
            ','.join(sorted(user_ids or []))
        ]
        return '|'.join(key_parts)
    
    def _get_cached_analytics(self, cache_key: str) -> Optional[List[AnalyticsDataPoint]]:
        """Get analytics from cache"""
        if self.redis_client:
            cached = self.redis_client.get(f"analytics:{cache_key}")
            if cached:
                data = json.loads(cached)
                return [AnalyticsDataPoint(**point) for point in data]
        return None
    
    def _cache_analytics(self, cache_key: str, data: List[AnalyticsDataPoint]):
        """Cache analytics data"""
        if self.redis_client:
            serialized_data = [asdict(point) for point in data]
            self.redis_client.setex(
                f"analytics:{cache_key}",
                self.cache_ttl,
                json.dumps(serialized_data, default=str)
            )
    
    async def _fetch_data(self, metric: AnalyticsMetric, time_range: AnalyticsTimeRange,
                         filters: Dict[str, Any], workspace_id: str, 
                         channel_ids: List[str], user_ids: List[str]) -> List[Dict]:
        """Fetch raw data from database"""
        try:
            # Convert time range to date range
            start_date, end_date = self._get_date_range(time_range)
            
            # Build query based on metric
            query = self._build_query(metric, start_date, end_date, filters, 
                                   workspace_id, channel_ids, user_ids)
            
            # Execute query
            if self.database:
                result = self.database.execute(query).fetchall()
                return [dict(row) for row in result]
            else:
                # Mock data for development
                return self._generate_mock_data(metric, start_date, end_date)
        
        except Exception as e:
            logger.error(f"Error fetching data: {e}")
            return []
    
    def _get_date_range(self, time_range: AnalyticsTimeRange) -> Tuple[datetime, datetime]:
        """Get start and end dates for time range"""
        now = datetime.utcnow()
        
        if time_range == AnalyticsTimeRange.TODAY:
            start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = now
        elif time_range == AnalyticsTimeRange.YESTERDAY:
            yesterday = now - timedelta(days=1)
            start_date = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
            end_date = yesterday.replace(hour=23, minute=59, second=59, microsecond=999999)
        elif time_range == AnalyticsTimeRange.LAST_7_DAYS:
            start_date = now - timedelta(days=7)
            end_date = now
        elif time_range == AnalyticsTimeRange.LAST_30_DAYS:
            start_date = now - timedelta(days=30)
            end_date = now
        elif time_range == AnalyticsTimeRange.LAST_90_DAYS:
            start_date = now - timedelta(days=90)
            end_date = now
        else:
            start_date = now - timedelta(days=30)  # Default to last 30 days
            end_date = now
        
        return start_date, end_date
    
    def _build_query(self, metric: AnalyticsMetric, start_date: datetime, end_date: datetime,
                    filters: Dict[str, Any], workspace_id: str,
                    channel_ids: List[str], user_ids: List[str]) -> str:
        """Build database query for metric"""
        # This would build appropriate SQL queries based on metric
        # For now, return a placeholder query
        return f"""
        SELECT * FROM slack_messages 
        WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'
        """
    
    def _group_by_hour(self, data: List[Dict], timestamp_field: str) -> Dict[datetime, List[Dict]]:
        """Group data by hour"""
        grouped = defaultdict(list)
        for item in data:
            timestamp = self._parse_timestamp(item.get(timestamp_field))
            if timestamp:
                hour_key = timestamp.replace(minute=0, second=0, microsecond=0)
                grouped[hour_key].append(item)
        return grouped
    
    def _group_by_day(self, data: List[Dict], timestamp_field: str) -> Dict[datetime, List[Dict]]:
        """Group data by day"""
        grouped = defaultdict(list)
        for item in data:
            timestamp = self._parse_timestamp(item.get(timestamp_field))
            if timestamp:
                day_key = timestamp.replace(hour=0, minute=0, second=0, microsecond=0)
                grouped[day_key].append(item)
        return grouped
    
    def _group_by_raw_timestamp(self, data: List[Dict], timestamp_field: str = 'timestamp') -> Dict[datetime, List[Dict]]:
        """Group data by raw timestamp"""
        grouped = defaultdict(list)
        for item in data:
            timestamp = self._parse_timestamp(item.get(timestamp_field))
            if timestamp:
                grouped[timestamp].append(item)
        return grouped
    
    def _parse_timestamp(self, timestamp_str: str) -> Optional[datetime]:
        """Parse timestamp string to datetime"""
        try:
            if not timestamp_str:
                return None
            
            # Handle Unix timestamp
            if timestamp_str.replace('.', '').isdigit():
                timestamp_float = float(timestamp_str)
                return datetime.fromtimestamp(timestamp_float, tz=timezone.utc)
            
            # Handle ISO string
            try:
                return datetime.fromisoformat(timestamp_str.replace('Z', '+00:00'))
            except:
                # Try other formats
                return datetime.strptime(timestamp_str, '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc)
        
        except Exception:
            return None
    
    def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text (placeholder)"""
        # Simple sentiment analysis (placeholder)
        positive_words = ['good', 'great', 'awesome', 'excellent', 'amazing', 'love', 'like']
        negative_words = ['bad', 'terrible', 'awful', 'hate', 'dislike', 'poor', 'worst']
        
        text_lower = text.lower()
        positive_count = sum(1 for word in positive_words if word in text_lower)
        negative_count = sum(1 for word in negative_words if word in text_lower)
        
        total_words = len(text.split())
        if total_words == 0:
            return 0
        
        # Simple sentiment score between -1 and 1
        sentiment = (positive_count - negative_count) / total_words
        return max(-1, min(1, sentiment))
    
    def _get_sentiment_distribution(self, sentiments: List[float]) -> Dict[str, float]:
        """Get sentiment distribution"""
        if not sentiments:
            return {'positive': 0, 'neutral': 0, 'negative': 0}
        
        positive = sum(1 for s in sentiments if s > 0.1)
        negative = sum(1 for s in sentiments if s < -0.1)
        neutral = len(sentiments) - positive - negative
        
        total = len(sentiments)
        return {
            'positive': positive / total,
            'neutral': neutral / total,
            'negative': negative / total
        }
    
    def _extract_topics(self, text: str) -> List[str]:
        """Extract topics from text (placeholder)"""
        # Simple topic extraction (placeholder)
        topics = []
        
        # Look for hashtags
        hashtags = re.findall(r'#(\w+)', text)
        topics.extend(hashtags)
        
        # Look for common keywords (placeholder)
        keywords = ['project', 'deadline', 'meeting', 'review', 'update', 'feature', 'bug']
        text_lower = text.lower()
        
        for keyword in keywords:
            if keyword in text_lower:
                topics.append(keyword)
        
        return topics
    
    def _calculate_score(self, data: List[AnalyticsDataPoint], reverse: bool = False) -> float:
        """Calculate score from data points"""
        if not data:
            return 0
        
        values = [float(point.value) for point in data]
        avg_value = statistics.mean(values)
        
        # Normalize to 0-1 scale (placeholder)
        if reverse:
            return max(0, 1 - avg_value / max(values) if values else 0)
        else:
            return min(1, avg_value / max(values) if values else 0)
    
    def _calculate_trends(self, data_series: List[Tuple[str, List[AnalyticsDataPoint]]]) -> Dict[str, Any]:
        """Calculate trends for data series"""
        trends = {}
        
        for name, data in data_series:
            if len(data) < 2:
                trends[f'{name}_trend'] = 'insufficient_data'
                continue
            
            # Simple trend calculation
            first_half = data[:len(data)//2]
            second_half = data[len(data)//2:]
            
            first_avg = statistics.mean([float(point.value) for point in first_half])
            second_avg = statistics.mean([float(point.value) for point in second_half])
            
            if second_avg > first_avg * 1.1:
                trend = 'increasing'
            elif second_avg < first_avg * 0.9:
                trend = 'decreasing'
            else:
                trend = 'stable'
            
            trends[f'{name}_trend'] = trend
            trends[f'{name}_change_percent'] = ((second_avg - first_avg) / first_avg * 100) if first_avg else 0
        
        return trends
    
    def _generate_mock_data(self, metric: AnalyticsMetric, start_date: datetime, end_date: datetime) -> List[Dict]:
        """Generate mock data for development"""
        import random
        
        mock_data = []
        current_date = start_date
        
        while current_date <= end_date:
            # Generate random data based on metric
            if metric == AnalyticsMetric.MESSAGE_VOLUME:
                value = random.randint(50, 500)
            elif metric == AnalyticsMetric.USER_ACTIVITY:
                value = random.randint(10, 100)
            elif metric == AnalyticsMetric.ENGAGEMENT:
                value = random.randint(20, 200)
            elif metric == AnalyticsMetric.RESPONSE_TIME:
                value = random.uniform(1, 30)
            else:
                value = random.randint(0, 100)
            
            mock_data.append({
                'timestamp': current_date.isoformat(),
                'value': value,
                'workspace_id': 'mock_workspace',
                'channel_id': 'mock_channel',
                'user_id': f'user_{random.randint(1, 50)}'
            })
            
            current_date += timedelta(hours=1)
        
        return mock_data

# Global analytics engine instance
slack_analytics_engine = SlackAnalyticsEngine({
    'database': None,  # Would be actual database connection
    'redis_client': None,  # Would be actual Redis client
    'cache_ttl': 300,
    'sentiment_analyzer': None,  # Would be actual sentiment analyzer
    'prediction_models': {}  # Would be actual ML models
})