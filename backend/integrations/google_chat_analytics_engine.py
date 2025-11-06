"""
ATOM Google Chat Analytics Engine
Comprehensive analytics for Google Chat within unified communication ecosystem
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

class GoogleChatAnalyticsMetric(Enum):
    """Google Chat analytics metrics"""
    MESSAGE_COUNT = "message_count"
    ACTIVE_USERS = "active_users"
    MESSAGE_FREQUENCY = "message_frequency"
    THREAD_CREATION = "thread_creation"
    CARD_INTERACTIONS = "card_interactions"
    BOT_MESSAGE_COUNT = "bot_message_count"
    HUMAN_MESSAGE_COUNT = "human_message_count"
    SPACE_ACTIVITY = "space_activity"
    USER_ENGAGEMENT = "user_engagement"
    RESPONSE_TIME = "response_time"
    REACTION_COUNT = "reaction_count"

class GoogleChatAnalyticsTimeRange(Enum):
    """Google Chat analytics time ranges"""
    LAST_24_HOURS = "last_24_hours"
    LAST_7_DAYS = "last_7_days"
    LAST_30_DAYS = "last_30_days"
    LAST_90_DAYS = "last_90_days"
    CUSTOM = "custom"

class GoogleChatAnalyticsGranularity(Enum):
    """Google Chat analytics granularity"""
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    YEAR = "year"

@dataclass
class GoogleChatAnalyticsDataPoint:
    """Google Chat analytics data point"""
    timestamp: datetime
    metric: GoogleChatAnalyticsMetric
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

class GoogleChatAnalyticsEngine:
    """Google Chat analytics engine with unified ecosystem integration"""
    
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
        
        logger.info("Google Chat Analytics Engine initialized")
    
    def _init_aggregation_patterns(self):
        """Initialize aggregation patterns for different metrics"""
        self.aggregation_patterns = {
            GoogleChatAnalyticsMetric.MESSAGE_COUNT: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'count', 'avg', 'min', 'max'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.ACTIVE_USERS: {
                'default_aggregation': 'count_distinct',
                'supported_aggregations': ['count_distinct', 'count'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.MESSAGE_FREQUENCY: {
                'default_aggregation': 'avg',
                'supported_aggregations': ['avg', 'min', 'max', 'median'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.THREAD_CREATION: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.CARD_INTERACTIONS: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum', 'avg'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.BOT_MESSAGE_COUNT: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum', 'avg'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.HUMAN_MESSAGE_COUNT: {
                'default_aggregation': 'count',
                'supported_aggregations': ['count', 'sum', 'avg'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.SPACE_ACTIVITY: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'avg', 'min', 'max'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.USER_ENGAGEMENT: {
                'default_aggregation': 'avg',
                'supported_aggregations': ['avg', 'min', 'max', 'median'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.RESPONSE_TIME: {
                'default_aggregation': 'avg',
                'supported_aggregations': ['avg', 'min', 'max', 'median'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            },
            GoogleChatAnalyticsMetric.REACTION_COUNT: {
                'default_aggregation': 'sum',
                'supported_aggregations': ['sum', 'count', 'avg'],
                'granularity_mapping': {
                    GoogleChatAnalyticsGranularity.HOUR: 'date_trunc(\'hour\', timestamp)',
                    GoogleChatAnalyticsGranularity.DAY: 'date_trunc(\'day\', timestamp)',
                    GoogleChatAnalyticsGranularity.WEEK: 'date_trunc(\'week\', timestamp)',
                    GoogleChatAnalyticsGranularity.MONTH: 'date_trunc(\'month\', timestamp)'
                }
            }
        }
    
    async def get_analytics(self, metric: GoogleChatAnalyticsMetric, 
                          time_range: GoogleChatAnalyticsTimeRange,
                          granularity: GoogleChatAnalyticsGranularity,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None,
                          space_ids: List[str] = None,
                          user_ids: List[str] = None) -> List[GoogleChatAnalyticsDataPoint]:
        """Get Google Chat analytics data"""
        try:
            # Generate cache key
            cache_key = self._generate_cache_key(
                metric, time_range, granularity, filters, workspace_id, space_ids, user_ids
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
                filters, workspace_id, space_ids, user_ids
            )
            
            # Cache result
            self._cache_result(cache_key, data_points)
            
            return data_points
        
        except Exception as e:
            logger.error(f"Error getting Google Chat analytics: {e}")
            return []
    
    async def _fetch_analytics_data(self, metric: GoogleChatAnalyticsMetric,
                                 start_time: datetime, end_time: datetime,
                                 granularity: GoogleChatAnalyticsGranularity,
                                 filters: Dict[str, Any] = None,
                                 workspace_id: str = None,
                                 space_ids: List[str] = None,
                                 user_ids: List[str] = None) -> List[GoogleChatAnalyticsDataPoint]:
        """Fetch analytics data from database"""
        try:
            # Build query based on metric
            query = await self._build_analytics_query(
                metric, start_time, end_time, granularity,
                filters, workspace_id, space_ids, user_ids
            )
            
            if not self.db:
                # Mock data for development
                return await self._generate_mock_analytics_data(metric, start_time, end_time, granularity)
            
            # Execute query
            result = self.db.execute(query['sql'], query['params']).fetchall()
            
            # Convert to data points
            data_points = []
            for row in result:
                data_point = GoogleChatAnalyticsDataPoint(
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
    
    async def _build_analytics_query(self, metric: GoogleChatAnalyticsMetric,
                                  start_time: datetime, end_time: datetime,
                                  granularity: GoogleChatAnalyticsGranularity,
                                  filters: Dict[str, Any] = None,
                                  workspace_id: str = None,
                                  space_ids: List[str] = None,
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
                where_conditions.append("workspace_id = ?")
                params.append(workspace_id)
            
            if space_ids:
                placeholders = ','.join(['?' for _ in space_ids])
                where_conditions.append(f"space_id IN ({placeholders})")
                params.extend(space_ids)
            
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
            base_table = "google_chat_messages"
            time_expr = pattern['granularity_mapping'][granularity]
            
            # Metric-specific queries
            if metric == GoogleChatAnalyticsMetric.MESSAGE_COUNT:
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
            
            elif metric == GoogleChatAnalyticsMetric.ACTIVE_USERS:
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
            
            elif metric == GoogleChatAnalyticsMetric.BOT_MESSAGE_COUNT:
                where_conditions.append("sender_type = 'BOT'")
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
            
            elif metric == GoogleChatAnalyticsMetric.HUMAN_MESSAGE_COUNT:
                where_conditions.append("sender_type = 'HUMAN'")
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
            
            elif metric == GoogleChatAnalyticsMetric.THREAD_CREATION:
                # Count messages with thread_id but no reply_to_id (thread starters)
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(*) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                AND thread_id IS NOT NULL 
                AND reply_to_id IS NULL
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == GoogleChatAnalyticsMetric.CARD_INTERACTIONS:
                # Count messages with card interactions
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    COUNT(*) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM {base_table}
                WHERE {' AND '.join(where_conditions)}
                AND (json_extract(integration_data, '$.action_response') IS NOT NULL
                     OR json_extract(integration_data, '$.arguments') IS NOT NULL)
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == GoogleChatAnalyticsMetric.RESPONSE_TIME:
                # Calculate average response time
                sql = f"""
                SELECT 
                    {time_expr} as timestamp,
                    AVG(response_time) as value,
                    {{dimensions}} as dimensions,
                    {{metadata}} as metadata
                FROM (
                    SELECT 
                        m1.timestamp,
                        (julianday(m2.timestamp) - julianday(m1.timestamp)) * 86400 as response_time
                    FROM {base_table} m1
                    JOIN {base_table} m2 ON m1.thread_id = m2.thread_id 
                        AND m2.timestamp > m1.timestamp
                        AND m2.reply_to_id = m1.message_id
                    WHERE {' AND '.join(where_conditions)}
                )
                GROUP BY {time_expr}
                ORDER BY timestamp
                """
            
            elif metric == GoogleChatAnalyticsMetric.REACTION_COUNT:
                # Count reactions from integration_data
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
    
    async def _generate_mock_analytics_data(self, metric: GoogleChatAnalyticsMetric,
                                        start_time: datetime, end_time: datetime,
                                        granularity: GoogleChatAnalyticsGranularity) -> List[GoogleChatAnalyticsDataPoint]:
        """Generate mock analytics data for development"""
        try:
            data_points = []
            
            # Generate time intervals
            current_time = start_time
            interval_delta = self._get_interval_delta(granularity)
            
            while current_time <= end_time:
                # Generate mock value based on metric
                mock_value = self._generate_mock_value(metric, current_time)
                
                data_point = GoogleChatAnalyticsDataPoint(
                    timestamp=current_time,
                    metric=metric,
                    value=mock_value,
                    dimensions={
                        'workspace_id': 'mock_workspace',
                        'space_id': 'mock_space',
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
    
    def _get_interval_delta(self, granularity: GoogleChatAnalyticsGranularity) -> timedelta:
        """Get time delta for given granularity"""
        mapping = {
            GoogleChatAnalyticsGranularity.HOUR: timedelta(hours=1),
            GoogleChatAnalyticsGranularity.DAY: timedelta(days=1),
            GoogleChatAnalyticsGranularity.WEEK: timedelta(weeks=1),
            GoogleChatAnalyticsGranularity.MONTH: timedelta(days=30)
        }
        return mapping.get(granularity, timedelta(days=1))
    
    def _generate_mock_value(self, metric: GoogleChatAnalyticsMetric, timestamp: datetime) -> float:
        """Generate mock value for metric based on time patterns"""
        
        # Base values for different metrics
        base_values = {
            GoogleChatAnalyticsMetric.MESSAGE_COUNT: 100,
            GoogleChatAnalyticsMetric.ACTIVE_USERS: 25,
            GoogleChatAnalyticsMetric.MESSAGE_FREQUENCY: 4.0,
            GoogleChatAnalyticsMetric.THREAD_CREATION: 15,
            GoogleChatAnalyticsMetric.CARD_INTERACTIONS: 8,
            GoogleChatAnalyticsMetric.BOT_MESSAGE_COUNT: 20,
            GoogleChatAnalyticsMetric.HUMAN_MESSAGE_COUNT: 80,
            GoogleChatAnalyticsMetric.SPACE_ACTIVITY: 150,
            GoogleChatAnalyticsMetric.USER_ENGAGEMENT: 0.65,
            GoogleChatAnalyticsMetric.RESPONSE_TIME: 180.0,  # seconds
            GoogleChatAnalyticsMetric.REACTION_COUNT: 25
        }
        
        base_value = base_values.get(metric, 50)
        
        # Add time-based patterns
        hour = timestamp.hour
        day_of_week = timestamp.weekday()
        
        # Work hours (9-17) multiplier
        work_hour_multiplier = 1.5 if 9 <= hour <= 17 else 0.7
        
        # Weekday multiplier
        weekday_multiplier = 1.2 if 0 <= day_of_week <= 4 else 0.8  # Mon-Fri
        
        # Add randomness
        random_multiplier = 0.8 + (hash(timestamp.isoformat()) % 10) / 10
        
        # Calculate final value
        final_value = base_value * work_hour_multiplier * weekday_multiplier * random_multiplier
        
        return max(0, final_value)
    
    def _get_time_range_boundaries(self, time_range: GoogleChatAnalyticsTimeRange) -> Tuple[datetime, datetime]:
        """Get start and end time for time range"""
        now = datetime.utcnow()
        
        mapping = {
            GoogleChatAnalyticsTimeRange.LAST_24_HOURS: (now - timedelta(hours=24), now),
            GoogleChatAnalyticsTimeRange.LAST_7_DAYS: (now - timedelta(days=7), now),
            GoogleChatAnalyticsTimeRange.LAST_30_DAYS: (now - timedelta(days=30), now),
            GoogleChatAnalyticsTimeRange.LAST_90_DAYS: (now - timedelta(days=90), now)
        }
        
        return mapping.get(time_range, (now - timedelta(days=7), now))
    
    def _generate_cache_key(self, metric: GoogleChatAnalyticsTimeRange,
                          time_range: GoogleChatAnalyticsTimeRange,
                          granularity: GoogleChatAnalyticsGranularity,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None,
                          space_ids: List[str] = None,
                          user_ids: List[str] = None) -> str:
        """Generate cache key for analytics request"""
        
        key_parts = [
            'google_chat_analytics',
            metric.value,
            time_range.value,
            granularity.value
        ]
        
        if workspace_id:
            key_parts.append(f"ws:{workspace_id}")
        
        if space_ids:
            key_parts.append(f"spaces:{','.join(sorted(space_ids))}")
        
        if user_ids:
            key_parts.append(f"users:{','.join(sorted(user_ids))}")
        
        if filters:
            filter_str = json.dumps(filters, sort_keys=True)
            key_parts.append(f"filters:{filter_str}")
        
        return '|'.join(key_parts)
    
    def _get_from_cache(self, cache_key: str) -> Optional[List[GoogleChatAnalyticsDataPoint]]:
        """Get analytics data from cache"""
        try:
            if not self.redis_client:
                return None
            
            cached_data = self.redis_client.get(cache_key)
            if cached_data:
                data = json.loads(cached_data)
                return [
                    GoogleChatAnalyticsDataPoint(
                        timestamp=datetime.fromisoformat(point['timestamp'].replace('Z', '+00:00')),
                        metric=GoogleChatAnalyticsMetric(point['metric']),
                        value=point['value'],
                        dimensions=point['dimensions'],
                        metadata=point['metadata']
                    )
                    for point in data
                ]
        
        except Exception as e:
            logger.error(f"Error getting analytics from cache: {e}")
        
        return None
    
    def _cache_result(self, cache_key: str, data_points: List[GoogleChatAnalyticsDataPoint]):
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
    
    async def get_top_spaces(self, metric: GoogleChatAnalyticsMetric,
                          time_range: GoogleChatAnalyticsTimeRange,
                          limit: int = 10,
                          filters: Dict[str, Any] = None,
                          workspace_id: str = None) -> List[Dict[str, Any]]:
        """Get top spaces by metric"""
        try:
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            if not self.db:
                # Return mock data
                return await self._generate_mock_top_spaces(metric, limit)
            
            # Build query for top spaces
            pattern = self.aggregation_patterns.get(metric)
            if not pattern:
                return []
            
            sql = f"""
            SELECT 
                space_id,
                space_name,
                COUNT(*) as value,
                AVG(CASE WHEN sender_type = 'HUMAN' THEN 1 ELSE 0 END) as human_ratio
            FROM google_chat_messages
            WHERE timestamp >= ? AND timestamp <= ?
            {f"AND workspace_id = ?" if workspace_id else ""}
            GROUP BY space_id, space_name
            ORDER BY value DESC
            LIMIT ?
            """
            
            params = [start_time.isoformat(), end_time.isoformat()]
            if workspace_id:
                params.append(workspace_id)
            params.append(limit)
            
            result = self.db.execute(sql, params).fetchall()
            
            return [
                {
                    'space_id': row['space_id'],
                    'space_name': row['space_name'],
                    'value': row['value'],
                    'metric': metric.value,
                    'human_ratio': row['human_ratio'],
                    'time_range': time_range.value
                }
                for row in result
            ]
        
        except Exception as e:
            logger.error(f"Error getting top spaces: {e}")
            return []
    
    async def _generate_mock_top_spaces(self, metric: GoogleChatAnalyticsMetric,
                                      limit: int) -> List[Dict[str, Any]]:
        """Generate mock top spaces data"""
        
        mock_spaces = [
            "General Discussion",
            "Project Alpha",
            "Engineering Team",
            "Marketing Updates",
            "Design Reviews",
            "Customer Support",
            "DevOps Corner",
            "Product Planning",
            "Sales Pipeline",
            "HR Announcements"
        ]
        
        top_spaces = []
        for i, space_name in enumerate(mock_spaces[:limit]):
            value = (limit - i) * 15 + (hash(space_name) % 20)
            
            top_spaces.append({
                'space_id': f"mock_space_{i}",
                'space_name': space_name,
                'value': value,
                'metric': metric.value,
                'human_ratio': 0.75 + (hash(space_name) % 25) / 100,
                'time_range': 'mock_data'
            })
        
        return top_spaces
    
    async def get_user_activity_summary(self, user_id: str, time_range: GoogleChatAnalyticsTimeRange) -> Dict[str, Any]:
        """Get activity summary for specific user"""
        try:
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            if not self.db:
                # Return mock data
                return {
                    'user_id': user_id,
                    'message_count': 150,
                    'spaces_participated': 5,
                    'threads_created': 12,
                    'reactions_given': 25,
                    'card_interactions': 8,
                    'avg_response_time': 180,
                    'most_active_hours': [10, 14, 16],
                    'engagement_score': 0.78,
                    'time_range': time_range.value
                }
            
            # Build query for user activity
            sql = """
            SELECT 
                COUNT(*) as message_count,
                COUNT(DISTINCT space_id) as spaces_participated,
                COUNT(CASE WHEN thread_id IS NOT NULL AND reply_to_id IS NULL THEN 1 END) as threads_created,
                SUM(
                    CASE 
                        WHEN json_extract(integration_data, '$.reactions') IS NOT NULL
                        THEN json_array_length(json_extract(integration_data, '$.reactions'))
                        ELSE 0
                    END
                ) as reactions_given,
                COUNT(CASE WHEN json_extract(integration_data, '$.action_response') IS NOT NULL THEN 1 END) as card_interactions,
                AVG(message_length) as avg_message_length
            FROM google_chat_messages
            WHERE user_id = ? AND timestamp >= ? AND timestamp <= ?
            """
            
            result = self.db.execute(sql, [user_id, start_time.isoformat(), end_time.isoformat()]).fetchone()
            
            # Get hourly activity pattern
            hourly_sql = """
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as message_count
            FROM google_chat_messages
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
                'spaces_participated': result['spaces_participated'] or 0,
                'threads_created': result['threads_created'] or 0,
                'reactions_given': result['reactions_given'] or 0,
                'card_interactions': result['card_interactions'] or 0,
                'avg_message_length': result['avg_message_length'] or 0,
                'most_active_hours': most_active_hours,
                'engagement_score': min(1.0, (result['message_count'] or 0) / 200),  # Normalized score
                'time_range': time_range.value
            }
        
        except Exception as e:
            logger.error(f"Error getting user activity summary: {e}")
            return {}
    
    async def get_space_activity_report(self, space_id: str, time_range: GoogleChatAnalyticsTimeRange) -> Dict[str, Any]:
        """Get comprehensive activity report for space"""
        try:
            start_time, end_time = self._get_time_range_boundaries(time_range)
            
            if not self.db:
                # Return mock data
                return {
                    'space_id': space_id,
                    'total_messages': 1250,
                    'active_users': 25,
                    'new_threads': 85,
                    'card_interactions': 120,
                    'bot_messages': 250,
                    'human_messages': 1000,
                    'avg_response_time': 165,
                    'peak_activity_hour': 14,
                    'top_contributors': [
                        {'user_name': 'John Doe', 'message_count': 180},
                        {'user_name': 'Jane Smith', 'message_count': 150},
                        {'user_name': 'Bob Wilson', 'message_count': 120}
                    ],
                    'engagement_trend': 'increasing',
                    'time_range': time_range.value
                }
            
            # Get overall metrics
            metrics_sql = """
            SELECT 
                COUNT(*) as total_messages,
                COUNT(DISTINCT user_id) as active_users,
                COUNT(CASE WHEN thread_id IS NOT NULL AND reply_to_id IS NULL THEN 1 END) as new_threads,
                COUNT(CASE WHEN json_extract(integration_data, '$.action_response') IS NOT NULL THEN 1 END) as card_interactions,
                COUNT(CASE WHEN sender_type = 'BOT' THEN 1 END) as bot_messages,
                COUNT(CASE WHEN sender_type = 'HUMAN' THEN 1 END) as human_messages,
                AVG(message_length) as avg_message_length
            FROM google_chat_messages
            WHERE space_id = ? AND timestamp >= ? AND timestamp <= ?
            """
            
            metrics_result = self.db.execute(metrics_sql, [space_id, start_time.isoformat(), end_time.isoformat()]).fetchone()
            
            # Get peak activity hour
            peak_sql = """
            SELECT 
                strftime('%H', timestamp) as hour,
                COUNT(*) as message_count
            FROM google_chat_messages
            WHERE space_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY hour
            ORDER BY message_count DESC
            LIMIT 1
            """
            
            peak_result = self.db.execute(peak_sql, [space_id, start_time.isoformat(), end_time.isoformat()]).fetchone()
            
            # Get top contributors
            contributors_sql = """
            SELECT 
                user_name,
                COUNT(*) as message_count
            FROM google_chat_messages
            WHERE space_id = ? AND timestamp >= ? AND timestamp <= ?
            GROUP BY user_id, user_name
            ORDER BY message_count DESC
            LIMIT 5
            """
            
            contributors_result = self.db.execute(contributors_sql, [space_id, start_time.isoformat(), end_time.isoformat()]).fetchall()
            
            return {
                'space_id': space_id,
                'total_messages': metrics_result['total_messages'] or 0,
                'active_users': metrics_result['active_users'] or 0,
                'new_threads': metrics_result['new_threads'] or 0,
                'card_interactions': metrics_result['card_interactions'] or 0,
                'bot_messages': metrics_result['bot_messages'] or 0,
                'human_messages': metrics_result['human_messages'] or 0,
                'avg_message_length': metrics_result['avg_message_length'] or 0,
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
            logger.error(f"Error getting space activity report: {e}")
            return {}
    
    async def export_analytics_data(self, metric: GoogleChatAnalyticsMetric,
                                 time_range: GoogleChatAnalyticsTimeRange,
                                 granularity: GoogleChatAnalyticsGranularity,
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
                    'filename': f"google_chat_{metric.value}_{time_range.value}.csv"
                }
            
            elif format.lower() == 'json':
                json_data = json.dumps([point.to_dict() for point in data_points], indent=2)
                return {
                    'ok': True,
                    'format': 'json',
                    'data': json_data,
                    'filename': f"google_chat_{metric.value}_{time_range.value}.json"
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
            logger.error(f"Error exporting analytics data: {e}")
            return {'ok': False, 'error': str(e)}
    
    def _convert_to_csv(self, data_points: List[GoogleChatAnalyticsDataPoint]) -> str:
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
            cache_keys = self.redis_client.keys("google_chat_analytics*")
            
            if cache_keys:
                self.redis_client.delete(*cache_keys)
                logger.info(f"Cleared {len(cache_keys)} analytics cache entries")
            
        except Exception as e:
            logger.error(f"Error clearing analytics cache: {e}")
    
    def get_engine_info(self) -> Dict[str, Any]:
        """Get analytics engine information"""
        return {
            "name": "Google Chat Analytics Engine",
            "version": "3.0.0",
            "description": "Comprehensive analytics for Google Chat with unified ecosystem integration",
            "supported_metrics": [metric.value for metric in GoogleChatAnalyticsMetric],
            "supported_time_ranges": [range.value for range in GoogleChatAnalyticsTimeRange],
            "supported_granularities": [gran.value for gran in GoogleChatAnalyticsGranularity],
            "cache_enabled": self.redis_client is not None,
            "cache_ttl": self.cache_ttl,
            "aggregation_patterns": list(self.aggregation_patterns.keys()),
            "status": "ACTIVE"
        }

# Global analytics engine instance
google_chat_analytics_engine = GoogleChatAnalyticsEngine({
    'database': None,  # Would be actual database connection
    'redis': {
        'enabled': os.getenv('REDIS_ENABLED', 'false').lower() == 'true',
        'client': None  # Would be actual Redis client
    },
    'cache_ttl': 300  # 5 minutes
})