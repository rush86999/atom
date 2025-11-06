"""
ATOM Discord Analytics Engine
Comprehensive analytics for Discord within unified communication ecosystem
"""

import os
import json
import logging
import asyncio
import time
import statistics
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple, Union
from dataclasses import dataclass, asdict
from enum import Enum
import httpx
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
import re

# Configure logging
logger = logging.getLogger(__name__)

class DiscordAnalyticsMetric(Enum):
    """Discord analytics metrics"""
    MESSAGE_COUNT = "message_count"
    ACTIVE_USERS = "active_users"
    VOICE_MINUTES = "voice_minutes"
    MESSAGE_FREQUENCY = "message_frequency"
    REACTION_COUNT = "reaction_count"
    FILE_UPLOADS = "file_uploads"
    BOT_MESSAGE_COUNT = "bot_message_count"
    HUMAN_MESSAGE_COUNT = "human_message_count"
    GUILD_ACTIVITY = "guild_activity"
    USER_ENGAGEMENT = "user_engagement"
    STREAM_MINUTES = "stream_minutes"
    ROLE_CHANGES = "role_changes"
    INVITE_USES = "invite_uses"
    BOOST_LEVEL = "boost_level"
    MODERATION_ACTIONS = "moderation_actions"

class DiscordAnalyticsTimeRange(Enum):
    """Discord analytics time ranges"""
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    CUSTOM = "custom"

class DiscordAnalyticsGranularity(Enum):
    """Discord analytics granularity"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

@dataclass
class DiscordAnalyticsDataPoint:
    """Discord analytics data point"""
    timestamp: datetime
    metric: DiscordAnalyticsMetric
    value: Union[int, float, str]
    dimensions: Dict[str, Any]
    metadata: Dict[str, Any]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            'timestamp': self.timestamp.isoformat(),
            'metric': self.metric.value,
            'value': self.value,
            'dimensions': self.dimensions,
            'metadata': self.metadata
        }

class DiscordAnalyticsEngine:
    """Discord analytics engine with unified ecosystem integration"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.db = config.get('database')
        self.redis_client = config.get('redis', {}).get('client')
        
        # Cache for analytics results
        self.analytics_cache = {}
        self.cache_ttl = config.get('cache_ttl', 300)  # 5 minutes
        
        # Performance tracking
        self.performance_metrics = {}
        
        # Initialize aggregation patterns
        self._init_aggregation_patterns()
        
        logger.info("Discord Analytics Engine initialized")
    
    def _init_aggregation_patterns(self):
        """Initialize aggregation patterns for different metrics"""
        self.aggregation_patterns = {
            DiscordAnalyticsMetric.MESSAGE_COUNT: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'count', 'avg', 'min', 'max'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.ACTIVE_USERS: {
                'default_aggregation': 'count_distinct',
                'supported_aggregations': ['count_distinct', 'count'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.VOICE_MINUTES: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'avg', 'min', 'max'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.REACTION_COUNT: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'count', 'avg'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.FILE_UPLOADS: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum', 'avg'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.BOT_MESSAGE_COUNT: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum', 'avg'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.HUMAN_MESSAGE_COUNT: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum', 'avg'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.GUILD_ACTIVITY: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'avg', 'min', 'max'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.USER_ENGAGEMENT: {
                'default_aggregation': 'avg',
                'supported_aggregations': ['avg', 'min', 'max', 'median'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            DiscordAnalyticsMetric.STREAM_MINUTES: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'avg', 'min', 'max'],
                'granularity_mapping': {
                    DiscordAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    DiscordAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    DiscordAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    DiscordAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            }
        }
    
    async def get_analytics(self, metric: DiscordAnalyticsMetric, 
                          time_range: DiscordAnalyticsTimeRange,
                          granularity: DiscordAnalyticsGranularity,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None,
                          guild_ids: List[str] = None,
                          channel_ids: List[str] = None,
                          user_ids: List[str] = None) -> List[DiscordAnalyticsDataPoint]:
        """Get Discord analytics data"""
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                metric, time_range, granularity, filters, workspace_id, guild_ids, channel_ids, user_ids
            )
            
            # Check cache
            cached_result = self._get_from_cache(cache_key)
            if cached_result:
                return cached_result
            
            # Get time range boundaries
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            # Get analytics data
            data_points = await self._fetch_analytics_data(
                metric, start_time, end_time, granularity, 
                filters, workspace_id, guild_ids, channel_ids, user_ids
            )
            
            # Cache result
            self._cache_result(cache_key, data_points)
            
            return data_points
        
        except Exception as e:
            logger.error(f"Error getting Discord analytics: {e}")
            return []
    
    async def _fetch_analytics_data(self, metric: DiscordAnalyticsMetric,
                                 start_time: datetime, end_time: datetime,
                                 granularity: DiscordAnalyticsGranularity,
                                 filters: Dict[str, Any] = None,
                                 workspace_id: str = None,
                                 guild_ids: List[str] = None,
                                 channel_ids: List[str] = None,
                                 user_ids: List[str] = None) -> List[DiscordAnalyticsDataPoint]:
        """Fetch analytics data from database"""
        try:
            # Build query based on metric
            query = await self._build_analytics_query(
                metric, start_time, end_time, granularity,
                filters, workspace_id, guild_ids, channel_ids, user_ids
            )
            
            if not self.db:
                # Mock data for development
                return await self._generate_mock_analytics_data(metric, start_time, end_time, granularity)
            
            # Execute query
            result = self.db.execute(query['sql'], query['params']).fetchall()
            
            # Convert to data points
            data_points = []
            for row in result:
                data_point = DiscordAnalyticsDataPoint(
                    timestamp=row['timestamp'],
                    metric=metric,
                    value=row['value'],
                    dimensions=row.get('dimensions', {}),
                    metadata=row.get('metadata', {})
                )
                data_points.append(data_point)
            
            return data_points
        
        except Exception as e:
            logger.error(f"Error fetching analytics data: {e}")
            return []
    
    async def _build_analytics_query(self, metric: DiscordAnalyticsMetric,
                                  start_time: datetime, end_time: datetime,
                                  granularity: DiscordAnalyticsGranularity,
                                  filters: Dict[str, Any] = None,
                                  workspace_id: str = None,
                                  guild_ids: List[str] = None,
                                  channel_ids: List[str] = None,
                                  user_ids: List[str] = None) -> Dict[str, Any]:
        """Build SQL query for analytics"""
        
        try:
            # Get aggregation pattern
            pattern = self.aggregation_patterns.get(metric)
            if not pattern:
                raise ValueError(f"Unsupported metric: {metric}")
            
            # Build WHERE conditions
            where_conditions = ["timestamp >= ?", "timestamp <= ?"]
            params = [start_time.isoformat(), end_time.isoformat()]
            
            if workspace_id:
                guild_id = workspace_id[8:] if workspace_id.startswith('discord_') else workspace_id
                where_conditions.append("guild_id = ?")
                params.append(guild_id)
            
            if guild_ids:
                placeholders = ','.join(['?' for _ in guild_ids])
                where_conditions.append(f"guild_id IN ({placeholders})")
                params.extend(guild_ids)
            
            if channel_ids:
                placeholders = ','.join(['?' for _ in channel_ids])
                where_conditions.append(f"channel_id IN ({placeholders})")
                params.extend(channel_ids)
            
            if user_ids:
                placeholders = ','.join(['?' for _ in user_ids])
                where_conditions.append(f"user_id IN ({placeholders})")
                params.extend(user_ids)
            
            # Add filters
            if filters:
                for key, value in filters.items():
                    if isinstance(value, list):
                        placeholders = ','.join(['?' for _ in value])
                        where_conditions.append(f"{key} IN ({placeholders})")
                        params.extend(value)
                    else:
                        where_conditions.append(f"{key} = ?")
                        params.append(value)
            
            # Build main query
            base_table = "discord_messages"
            time_expr = pattern['granularity_mapping'][granularity]
            
            # Metric-specific queries
            if metric == DiscordAnalyticsMetric.MESSAGE_COUNT:
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(*) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == DiscordAnalyticsMetric.ACTIVE_USERS:
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(DISTINCT user_id) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == DiscordAnalyticsMetric.BOT_MESSAGE_COUNT:
                where_conditions.append("is_bot = 1")
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(*) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == DiscordAnalyticsMetric.HUMAN_MESSAGE_COUNT:
                where_conditions.append("is_bot = 0")
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(*) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == DiscordAnalyticsMetric.REACTION_COUNT:
                # Count reactions from message data
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    SUM(
                        CASE 
                            WHEN json_extract(integration_data, '$.reactions') IS NOT NULL
                            THEN json_array_length(json_extract(integration_data, '$.reactions'))
                            ELSE 0
                        END
                    ) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == DiscordAnalyticsMetric.FILE_UPLOADS:
                # Count messages with attachments
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(CASE WHEN json_extract(integration_data, '$.attachments') IS NOT NULL THEN 1 END) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            else:
                # Default query for other metrics
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(*) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            # Replace dimension and metadata placeholders
            sql = sql.replace('{{dimensions}}', "'{}'").replace('{{metadata}}', "'{}'")
            
            return {'sql': sql, 'params': params}
        
        except Exception as e:
            logger.error(f"Error building analytics query: {e}")
            return {'sql': '', 'params': []}
    
    async def _generate_mock_analytics_data(self, metric: DiscordAnalyticsMetric,
                                        start_time: datetime, end_time: datetime,
                                        granularity: DiscordAnalyticsGranularity) -> List[DiscordAnalyticsDataPoint]:
        """Generate mock analytics data for development"""
        try:
            data_points = []
            
            # Generate time intervals
            current_time = start_time
            interval_delta = self._get_interval_delta(granularity)
            
            while current_time <= end_time:
                # Generate mock value based on metric
                mock_value = self._generate_mock_value(metric, current_time)
                
                data_point = DiscordAnalyticsDataPoint(
                    timestamp=current_time,
                    metric=metric,
                    value=mock_value,
                    dimensions={
                        'workspace_id': 'mock_workspace',
                        'guild_id': 'mock_guild',
                        'channel_type': 'text',
                        'metric_type': 'mock_data'
                    },
                    metadata={
                        'data_source': 'mock_generator',
                        'generation_time': datetime.utcnow().isoformat()
                    }
                )
                data_points.append(data_point)
                
                current_time += interval_delta
            
            return data_points
        
        except Exception as e:
            logger.error(f"Error generating mock analytics data: {e}")
            return []
    
    def _get_interval_delta(self, granularity: DiscordAnalyticsGranularity) -> timedelta:
        """Get time delta for given granularity"""
        mapping = {
            DiscordAnalyticsGranularity.HOUR: timedelta(hours=1),
            DiscordAnalyticsGranularity.DAY: timedelta(days=1),
            DiscordAnalyticsGranularity.WEEK: timedelta(weeks=1),
            DiscordAnalyticsGranularity.MONTH: timedelta(days=30)
        }
        return mapping.get(granularity, timedelta(days=1))
    
    def _generate_mock_value(self, metric: DiscordAnalyticsMetric, timestamp: datetime) -> float:
        """Generate mock value for metric based on time patterns"""
        
        # Base values for different metrics
        base_values = {
            DiscordAnalyticsMetric.MESSAGE_COUNT: 150,
            DiscordAnalyticsMetric.ACTIVE_USERS: 35,
            DiscordAnalyticsMetric.VOICE_MINUTES: 2400,
            DiscordAnalyticsMetric.REACTION_COUNT: 40,
            DiscordAnalyticsMetric.FILE_UPLOADS: 15,
            DiscordAnalyticsMetric.BOT_MESSAGE_COUNT: 30,
            DiscordAnalyticsMetric.HUMAN_MESSAGE_COUNT: 120,
            DiscordAnalyticsMetric.GUILD_ACTIVITY: 180,
            DiscordAnalyticsMetric.USER_ENGAGEMENT: 0.7,
            DiscordAnalyticsMetric.STREAM_MINUTES: 300
        }
        
        base_value = base_values.get(metric, 50)
        
        # Add time-based patterns for Discord
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        
        # Discord users are more active in evenings and weekends
        evening_multiplier = 1.5 if 18 <= hour <= 23 else 0.8 if 6 <= hour <= 12 else 1.0
        weekend_multiplier = 1.3 if day_of_week >= 5 else 0.9
        
        # Add randomness
        random_multiplier = 0.7 + (hash(timestamp.isoformat()) % 10) / 10
        
        # Calculate final value
        final_value = base_value * evening_multiplier * weekend_multiplier * random_multiplier
        
        return max(0, final_value)
    
    def _get_time_range_boundaries(self, time_range: DiscordAnalyticsTimeRange) -> Tuple[datetime, datetime]:
        """Get start and end time for time range"""
        now = datetime.utcnow()
        
        mapping = {
            DiscordAnalyticsTimeRange.LAST_24_HOURS: (now - timedelta(hours=24), now),
            DiscordAnalyticsTimeRange.LAST_7_DAYS: (now - timedelta(days=7), now),
            DiscordAnalyticsTimeRange.LAST_30_DAYS: (now - timedelta(days=30), now),
            DiscordAnalyticsTimeRange.LAST_90_DAYS: (now - timedelta(days=90), now)
        }
        
        return mapping.get(time_range, (now - timedelta(days=7), now))
    
    def _generate_cache_key(self, metric: DiscordAnalyticsMetric,
                          time_range: DiscordAnalyticsTimeRange,
                          granularity: DiscordAnalyticsGranularity,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None,
                          guild_ids: List[str] = None,
                          channel_ids: List[str] = None,
                          user_ids: List[str] = None) -> str:
        """Generate cache key for analytics request"""
        
        key_parts = [
            'discord_analytics',
            metric.value,
            time_range.value,
            granularity.value
        ]
        
        if workspace_id:
            key_parts.append(f"ws:{workspace_id}")
        
        if guild_ids:
            key_parts.append(f"guilds:{','.join(sorted(guild_ids))}")
        
        if channel_ids:
            key_parts.append(f"channels:{','.join(sorted(channel_ids))}")
        
        if user_ids:
            key_parts.append(f"users:{','.join(sorted(user_ids))}")
        
        if filters:
            filter_str = json.dumps(filters, sort_keys=True)
            key_parts.append(f"filters:{filter_str}")
        
        return '|'.join(key_parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[DiscordAnalyticsDataPoint]]:
        """Get analytics data from cache"""
        try:
            if not self.redis_client:
                return None
            
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return [
                    DiscordAnalyticsDataPoint(
                        timestamp=datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00')),
                        metric=DiscordAnalyticsMetric(point['metric']),
                        value=point['value'],
                        dimensions=point['dimensions'],
                        metadata=point['metadata']
                    )
                    for point in data
                ]
        
        except Exception as e:
            logger.error(f"Error getting analytics from cache: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, data_points: List[DiscordAnalyticsDataPoint]):
        """Cache analytics result"""
        try:
            if not self.redis_client or not data_points:
                return
            
            # Convert to JSON
            cache_data = json.dumps([point.to_dict() for point in data_points])
            
            # Cache with TTL
            self.redis_client.setex(cache_key, self.cache_ttl, cache_data)
        
        except Exception as e:
            logger.error(f"Error caching analytics result: {e}")
    
    async def get_top_guilds(self, metric: DiscordAnalyticsMetric,
                          time_range: DiscordAnalyticsTimeRange,
                          limit: int = 10,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None) -> List[Dict[str, Any]]:
        """Get top Discord guilds by metric"""
        try:
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            if not self.db:
                # Return mock data
                return await self._generate_mock_top_guilds(metric, limit)
            
            # Build query for top guilds
            pattern = self.aggregation_patterns.get(metric)
            if not pattern:
                return []
            
            sql = f"""
            SELECT 
                guild_id,
                guild_name,
                COUNT(*) as value,
                AVG(CASE WHEN is_bot = 0 THEN 1 ELSE 0 END) as human_ratio
            FROM discord_messages
            WHERE timestamp >= ? AND timestamp <= ?
            {f"AND guild_id = ?" if workspace_id else ""}
            GROUP BY guild_id, guild_name
            ORDER BY value DESC
            LIMIT ?
            """
            
            params = [start_time.isoformat(), end_time.isoformat()]
            if workspace_id:
                guild_id = workspace_id[8:] if workspace_id.startswith('discord_') else workspace_id
                params.append(guild_id)
            params.append(limit)
            
            result = self.db.execute(sql, params).fetchall()
            
            return [
                {
                    'guild_id': row['guild_id'],
                    'guild_name': row['guild_name'],
                    'value': row['value'],
                    'metric': metric.value,
                    'human_ratio': row['human_ratio'],
                    'time_range': time_range.value
                }
                for row in result
            ]
        
        except Exception as e:
            logger.error(f"Error getting top Discord guilds: {e}")
            return []
    
    async def _generate_mock_top_guilds(self, metric: DiscordAnalyticsMetric,
                                      limit: int) -> List[Dict[str, Any]]:
        """Generate mock top guilds data"""
        
        mock_guilds = [
            "Gaming Community",
            "Tech Hub",
            "Art & Design",
            "Music Lovers",
            "Study Group",
            "Developer Community",
            "Fitness & Health",
            "Book Club",
            "Movie Discussions",
            "Travel & Adventure"
        ]
        
        top_guilds = []
        for i, guild_name in enumerate(mock_guilds[:limit]):
            value = (limit - i) * 25 + (hash(guild_name) % 30)
            
            top_guilds.append({
                'guild_id': f"mock_guild_{i}",
                'guild_name': guild_name,
                'value': value,
                'metric': metric.value,
                'human_ratio': 0.8 + (hash(guild_name) % 20) / 100,
                'time_range': 'mock_data'
            })
        
        return top_guilds
    
    async def get_user_activity_summary(self, user_id: str, time_range: DiscordAnalyticsTimeRange) -> Dict[str, Any]:
        """Get activity summary for specific Discord user"""
        try:
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            if not self.db:
                # Return mock data
                return {
                    'user_id': user_id,
                    'message_count': 280,
                    'reactions_given': 45,
                    'files_uploaded': 12,
                    'voice_minutes': 3200,
                    'stream_minutes': 450,
                    'roles_changed': 3,
                    'most_active_channels': [
                        {'channel_name': 'general', 'message_count': 120},
                        {'channel_name': 'gaming', 'message_count': 85}
                    ],
                    'most_active_hours': [14, 20, 22],
                    'engagement_score': 0.82,
                    'is_bot': False,
                    'time_range': time_range.value
                }
            
            # Build query for user activity
            sql = """
            SELECT 
                COUNT(*) as message_count,
                COUNT(DISTINCT channel_id) as channels_participated,
                SUM(
                    CASE 
                        WHEN json_extract(integration_data, '$.reactions') IS NOT NULL
                        THEN json_array_length(json_extract(integration_data, '$.reactions'))
                        ELSE 0
                    END
                ) as reactions_given,
                SUM(
                    CASE 
                        WHEN json_extract(integration_data, '$.attachments') IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) as files_uploaded,
                AVG(message_length) as avg_message_length
            FROM discord_messages
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            """
            
            result = self.db.execute(sql, [user_id, start_time.isoformat(), end_time.isoformat()]).fetchone()
            
            # Get hourly activity pattern
            hourly_sql = """
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as message_count
            FROM discord_messages
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY hour
            ORDER BY message_count DESC
            LIMIT 3
            """
            
            hourly_result = self.db.execute(hourly_sql, [user_id, start_time.isoformat(), end_time.isoformat()]).fetchall()
            most_active_hours = [int(row['hour']) for row in hourly_result]
            
            return {
                'user_id': user_id,
                'message_count': result['message_count'] or 0,
                'channels_participated': result['channels_participated'] or 0,
                'reactions_given': result['reactions_given'] or 0,
                'files_uploaded': result['files_uploaded'] or 0,
                'avg_message_length': result['avg_message_length'] or 0,
                'voice_minutes': 0,  # Would get from voice states table
                'stream_minutes': 0,  # Would get from voice states table
                'most_active_hours': most_active_hours,
                'engagement_score': min(1.0, (result['message_count'] or 0) / 300),
                'time_range': time_range.value
            }
        
        except Exception as e:
            logger.error(f"Error getting Discord user activity summary: {e}")
            return {}
    
    async def get_guild_activity_report(self, guild_id: str, time_range: DiscordAnalyticsTimeRange) -> Dict[str, Any]:
        """Get comprehensive activity report for Discord guild"""
        try:
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            if not self.db:
                # Return mock data
                return {
                    'guild_id': guild_id,
                    'total_messages': 2450,
                    'active_users': 45,
                    'voice_minutes': 12000,
                    'bot_messages': 350,
                    'human_messages': 2100,
                    'reaction_count': 320,
                    'file_uploads': 85,
                    'stream_minutes': 1800,
                    'peak_activity_hour': 20,
                    'top_contributors': [
                        {'user_name': 'GameMaster', 'message_count': 320},
                        {'user_name': 'TechNerd', 'message_count': 280}
                    ],
                    'engagement_trend': 'increasing',
                    'boost_level': 2,
                    'features': ['COMMUNITY', 'NEWS', 'WELCOME_SCREEN_ENABLED'],
                    'time_range': time_range.value
                }
            
            # Get overall metrics
            metrics_sql = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as active_users,
                SUM(CASE WHEN is_bot = 1 THEN 1 END) as bot_messages,
                SUM(CASE WHEN is_bot = 0 THEN 1 END) as human_messages,
                SUM(
                    CASE 
                        WHEN json_extract(integration_data, '$.reactions') IS NOT NULL
                        THEN json_array_length(json_extract(integration_data, '$.reactions'))
                        ELSE 0
                    END
                ) as reaction_count,
                SUM(
                    CASE 
                        WHEN json_extract(integration_data, '$.attachments') IS NOT NULL
                        THEN 1
                        ELSE 0
                    END
                ) as file_uploads,
                AVG(message_length) as avg_message_length
            FROM discord_messages
            WHERE guild_id = ? AND timestamp >= ? AND timestamp <= ?
            """
            
            metrics_result = self.db.execute(metrics_sql, [guild_id, start_time.isoformat(), end_time.isoformat()]).fetchone()
            
            # Get peak activity hour
            peak_sql = """
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as message_count
            FROM discord_messages
            WHERE guild_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY hour
            ORDER BY message_count DESC
            LIMIT 1
            """
            
            peak_result = self.db.execute(peak_sql, [guild_id, start_time.isoformat(), end_time.isoformat()]).fetchone()
            
            # Get top contributors
            contributors_sql = """
            SELECT 
                user_name,
                COUNT(*) as message_count
            FROM discord_messages
            WHERE guild_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY user_id, user_name
            ORDER BY message_count DESC
            LIMIT 5
            """
            
            contributors_result = self.db.execute(contributors_sql, [guild_id, start_time.isoformat(), end_time.isoformat()]).fetchall()
            
            return {
                'guild_id': guild_id,
                'total_messages': metrics_result['total_messages'] or 0,
                'active_users': metrics_result['active_users'] or 0,
                'bot_messages': metrics_result['bot_messages'] or 0,
                'human_messages': metrics_result['human_messages'] or 0,
                'reaction_count': metrics_result['reaction_count'] or 0,
                'file_uploads': metrics_result['file_uploads'] or 0,
                'avg_message_length': metrics_result['avg_message_length'] or 0,
                'voice_minutes': 0,  # Would get from voice states
                'stream_minutes': 0,  # Would get from voice states
                'peak_activity_hour': int(peak_result['hour']) if peak_result else None,
                'top_contributors': [
                    {
                        'user_name': row['user_name'],
                        'message_count': row['message_count']
                    }
                    for row in contributors_result
                ],
                'engagement_trend': 'stable',  # Would calculate trend
                'time_range': time_range.value
            }
        
        except Exception as e:
            logger.error(f"Error getting Discord guild activity report: {e}")
            return {}
    
    async def get_voice_chat_analytics(self, guild_id: str, time_range: DiscordAnalyticsTimeRange) -> Dict[str, Any]:
        """Get voice chat analytics for Discord guild"""
        try:
            if not self.db:
                # Return mock data
                return {
                    'guild_id': guild_id,
                    'total_voice_minutes': 24000,
                    'average_voice_session': 45,
                    'peak_voice_users': 28,
                    'peak_voice_hour': 20,
                    'most_used_voice_channels': [
                        {'channel_name': 'General Voice', 'minutes': 8000},
                        {'channel_name': 'Gaming Voice', 'minutes': 6000}
                    ],
                    'streaming_minutes': 3600,
                    'unique_voice_users': 35,
                    'time_range': time_range.value
                }
            
            # This would query discord_voice_states table
            # For now, return mock data
            return await self._generate_mock_voice_analytics(guild_id, time_range)
        
        except Exception as e:
            logger.error(f"Error getting Discord voice chat analytics: {e}")
            return {}
    
    async def _generate_mock_voice_analytics(self, guild_id: str, time_range: DiscordAnalyticsTimeRange) -> Dict[str, Any]:
        """Generate mock voice analytics data"""
        
        mock_voice_channels = [
            "General Voice",
            "Gaming Voice", 
            "Study Room",
            "Music Lounge"
        ]
        
        total_minutes = 24000
        channel_minutes = total_minutes // len(mock_voice_channels)
        
        return {
            'guild_id': guild_id,
            'total_voice_minutes': total_minutes,
            'average_voice_session': 45,
            'peak_voice_users': 28,
            'peak_voice_hour': 20,
            'most_used_voice_channels': [
                {'channel_name': channel, 'minutes': channel_minutes + (hash(channel) % 1000)}
                for channel in mock_voice_channels
            ],
            'streaming_minutes': 3600,
            'unique_voice_users': 35,
            'time_range': time_range.value
        }
    
    async def export_analytics_data(self, metric: DiscordAnalyticsMetric,
                                 time_range: DiscordAnalyticsTimeRange,
                                 granularity: DiscordAnalyticsGranularity,
                                 format: str = 'csv',
                                 filters: Dict[str, Any] = None) -> Dict[str, Any]:
        """Export analytics data in various formats"""
        try:
            # Get analytics data
            data_points = await self.get_analytics(
                metric, time_range, granularity, filters
            )
            
            if not data_points:
                return {'ok': False, 'error': 'No data available for export'}
            
            # Convert to specified format
            if format.lower() == 'csv':
                csv_data = self._convert_to_csv(data_points)
                return {
                    'ok': True,
                    'format': 'csv',
                    'data': csv_data,
                    'filename': f"discord_{metric.value}_{time_range.value}.csv"
                }
            
            elif format.lower() == 'json':
                json_data = json.dumps([point.to_dict() for point in data_points], indent=2)
                return {
                    'ok': True,
                    'format': 'json',
                    'data': json_data,
                    'filename': f"discord_{metric.value}_{time_range.value}.json"
                }
            
            elif format.lower() == 'excel':
                # Would use pandas to create Excel file
                return {
                    'ok': False,
                    'error': 'Excel export not yet implemented'
                }
            
            else:
                return {'ok': False, 'error': f'Unsupported format: {format}'}
        
        except Exception as e:
            logger.error(f"Error exporting Discord analytics data: {e}")
            return {'ok': False, 'error': str(e)}
    
    def _convert_to_csv(self, data_points: List[DiscordAnalyticsDataPoint]) -> str:
        """Convert data points to CSV format"""
        try:
            if not data_points:
                return ""
            
            # CSV headers
            headers = ['timestamp', 'metric', 'value', 'dimensions', 'metadata']
            
            # CSV rows
            rows = []
            for point in data_points:
                row = [
                    point.timestamp.isoformat(),
                    point.metric.value,
                    str(point.value),
                    json.dumps(point.dimensions),
                    json.dumps(point.metadata)
                ]
                rows.append(','.join(f'"{field}"' for field in row))
            
            # Combine headers and rows
            csv_content = ','.join(headers) + '\n' + '\n'.join(rows)
            
            return csv_content
        
        except Exception as e:
            logger.error(f"Error converting to CSV: {e}")
            return ""
    
    async def clear_cache(self):
        """Clear analytics cache"""
        try:
            if not self.redis_client:
                return
            
            # Get all analytics cache keys
            cache_keys = self.redis_client.keys("discord_analytics*")
            
            if cache_keys:
                self.redis_client.delete(*cache_keys)
                logger.info(f"Cleared {len(cache_keys)} analytics cache entries")
            
        except Exception as e:
            logger.error(f"Error clearing Discord analytics cache: {e}")
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get analytics engine information"""
        return {
            "name": "Discord Analytics Engine",
            "version": "4.0.0",
            "description": "Comprehensive analytics for Discord with unified ecosystem integration",
            "supported_metrics": [metric.value for metric in DiscordAnalyticsMetric],
            "supported_time_ranges": [range.value for range in DiscordAnalyticsTimeRange],
            "supported_granularities": [gran.value for gran in DiscordAnalyticsGranularity],
            "cache_enabled": self.redis_client is not None,
            "cache_ttl": self.cache_ttl,
            "aggregation_patterns": list(self.aggregation_patterns.keys()),
            "features": [
                "message_analytics",
                "user_analytics",
                "voice_chat_analytics",
                "guild_analytics",
                "reaction_analytics",
                "file_upload_analytics",
                "bot_activity_tracking",
                "streaming_analytics"
            ],
            "status": "ACTIVE"
        }

# Global analytics engine instance
discord_analytics_engine = DiscordAnalyticsEngine({
    'database': None,  # Would be actual database connection
    'redis': {
        'enabled': os.getenv('REDIS_ENABLED', 'false').lower() == 'true',
        'client': None  # Would be actual Redis client
    },
    'cache_ttl': 300  # 5 minutes
})