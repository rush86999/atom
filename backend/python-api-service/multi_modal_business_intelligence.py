"""
ATOM Multi-Modal Business Intelligence Service
Advanced cross-modal analytics, aggregation, and dashboard integration
"""

import os
import json
import asyncio
import aiohttp
import hashlib
import uuid
import base64
from typing import Dict, List, Optional, Any, Tuple, Union, Set
from datetime import datetime, timedelta, date
from dataclasses import dataclass, asdict
from enum import Enum
import numpy as np
from loguru import logger
from collections import defaultdict, deque
import pandas as pd

# Multi-Modal Services
from vision_ai_service import create_vision_ai_service, VisionTask, VisionModel
from audio_ai_service import create_audio_ai_service, AudioTask, AudioModel
from cross_modal_ai_service import create_cross_modal_ai_service, CrossModalTask
from multi_modal_workflow_engine import create_multi_modal_workflow_engine, WorkflowExecution

# Existing Services
from advanced_ai_models_service import create_advanced_ai_models_service, AIModelType

class InsightType(Enum):
    """Business insight types"""
    TREND_ANALYSIS = "trend_analysis"
    ANOMALY_DETECTION = "anomaly_detection"
    CORRELATION_ANALYSIS = "correlation_analysis"
    PREDICTIVE_INSIGHTS = "predictive_insights"
    PERFORMANCE_METRICS = "performance_metrics"
    CROSS_MODAL_INSIGHTS = "cross_modal_insights"
    BUSINESS_INTELLIGENCE = "business_intelligence"
    OPERATIONAL_INSIGHTS = "operational_insights"
    FINANCIAL_INSIGHTS = "financial_insights"
    CUSTOMER_INSIGHTS = "customer_insights"

class TimeGranularity(Enum):
    """Time granularity for analytics"""
    REAL_TIME = "real_time"
    MINUTE = "minute"
    HOUR = "hour"
    DAY = "day"
    WEEK = "week"
    MONTH = "month"
    QUARTER = "quarter"
    YEAR = "year"

@dataclass
class MultimodalDataPoint:
    """Multimodal data point for analytics"""
    point_id: str
    timestamp: datetime
    modalities: Dict[str, Any]  # modality -> data
    metadata: Dict[str, Any]
    insights: Dict[str, Any]
    kpi_values: Dict[str, float]
    tags: List[str]
    
    def __post_init__(self):
        if self.modalities is None:
            self.modalities = {}
        if self.metadata is None:
            self.metadata = {}
        if self.insights is None:
            self.insights = {}
        if self.kpi_values is None:
            self.kpi_values = {}
        if self.tags is None:
            self.tags = []

@dataclass
class BusinessInsight:
    """Business insight from multimodal data"""
    insight_id: str
    insight_type: InsightType
    title: str
    description: str
    confidence: float
    impact_level: str  # "low", "medium", "high", "critical"
    supporting_data: Dict[str, Any]
    recommendations: List[str]
    time_window: Tuple[datetime, datetime]
    kpi_impact: Dict[str, float]
    modalities_used: List[str]
    generated_at: datetime
    
    def __post_init__(self):
        if self.supporting_data is None:
            self.supporting_data = {}
        if self.recommendations is None:
            self.recommendations = []
        if self.kpi_impact is None:
            self.kpi_impact = {}
        if self.modalities_used is None:
            self.modalities_used = []

@dataclass
class MultimodalDashboard:
    """Multimodal analytics dashboard configuration"""
    dashboard_id: str
    name: str
    description: str
    widgets: List[Dict[str, Any]]
    data_sources: List[str]
    time_filters: Dict[str, Any]
    kpi_definitions: Dict[str, Any]
    refresh_interval: Optional[int] = None  # seconds
    created_at: datetime = None
    updated_at: datetime = None
    
    def __post_init__(self):
        if self.widgets is None:
            self.widgets = []
        if self.data_sources is None:
            self.data_sources = []
        if self.time_filters is None:
            self.time_filters = {}
        if self.kpi_definitions is None:
            self.kpi_definitions = {}
        if self.created_at is None:
            self.created_at = datetime.utcnow()
        if self.updated_at is None:
            self.updated_at = datetime.utcnow()

@dataclass
class AnalyticsRequest:
    """Analytics request for multimodal business intelligence"""
    request_id: str
    insight_types: List[InsightType]
    time_window: Tuple[datetime, datetime]
    granularity: TimeGranularity
    filters: Dict[str, Any]
    kpi_names: List[str]
    modalities: List[str]
    options: Dict[str, Any]
    metadata: Dict[str, Any]
    timestamp: datetime = None
    
    def __post_init__(self):
        if self.insight_types is None:
            self.insight_types = []
        if self.filters is None:
            self.filters = {}
        if self.kpi_names is None:
            self.kpi_names = []
        if self.modalities is None:
            self.modalities = []
        if self.options is None:
            self.options = {}
        if self.metadata is None:
            self.metadata = {}
        if self.timestamp is None:
            self.timestamp = datetime.utcnow()

class MultiModalBusinessIntelligence:
    """Enterprise multimodal business intelligence service"""
    
    def __init__(self):
        # Initialize AI services
        self.vision_ai = create_vision_ai_service()
        self.audio_ai = create_audio_ai_service()
        self.cross_modal_ai = create_cross_modal_ai_service()
        self.advanced_ai = create_advanced_ai_models_service()
        self.workflow_engine = create_multi_modal_workflow_engine()
        
        # Data storage and analytics
        self.data_points = {}  # point_id -> MultimodalDataPoint
        self.insights = {}  # insight_id -> BusinessInsight
        self.dashboards = {}  # dashboard_id -> MultimodalDashboard
        self.time_series_data = defaultdict(list)  # timestamp -> list of point_ids
        
        # Analytics processing
        self.analytics_queue = asyncio.Queue()
        self.insight_cache = defaultdict(dict)  # insight_type -> time_hash -> insights
        
        # Performance tracking
        self.performance_metrics = {}
        
        # Background processors
        self.background_tasks = set()
        
        # Start background processors
        self._start_background_processors()
        
        logger.info("Multi-Modal Business Intelligence Service initialized")
    
    def _start_background_processors(self):
        """Start background processing tasks"""
        tasks = [
            self._process_analytics_loop(),
            self._generate_insights_loop(),
            self._update_dashboards_loop(),
            self._cleanup_data_loop(),
            self._update_metrics_loop()
        ]
        
        for task in tasks:
            background_task = asyncio.create_task(task)
            self.background_tasks.add(background_task)
            background_task.add_done_callback(self.background_tasks.discard)
    
    async def submit_data_point(self, data_point: MultimodalDataPoint) -> str:
        """Submit multimodal data point for analytics"""
        try:
            # Generate ID if not provided
            if not data_point.point_id:
                data_point.point_id = str(uuid.uuid4())
            
            # Store data point
            self.data_points[data_point.point_id] = data_point
            
            # Add to time series index
            self.time_series_data[data_point.timestamp].append(data_point.point_id)
            
            # Create analytics task for processing
            analytics_task = {
                "type": "data_point_analysis",
                "data_point_id": data_point.point_id,
                "timestamp": datetime.utcnow()
            }
            
            await self.analytics_queue.put(analytics_task)
            
            logger.info(f"Submitted data point {data_point.point_id} with modalities: {list(data_point.modalities.keys())}")
            return data_point.point_id
            
        except Exception as e:
            logger.error(f"Failed to submit data point: {e}")
            raise
    
    async def generate_analytics(self, request: AnalyticsRequest) -> Dict[str, Any]:
        """Generate comprehensive multimodal analytics"""
        try:
            logger.info(f"Generating analytics for request {request.request_id}")
            start_time = datetime.utcnow()
            
            # Collect relevant data points
            relevant_points = self._collect_relevant_data_points(request)
            
            # Generate insights for each requested type
            all_insights = []
            
            for insight_type in request.insight_types:
                insights = await self._generate_insights_by_type(
                    insight_type, 
                    relevant_points, 
                    request
                )
                all_insights.extend(insights)
            
            # Generate KPI analysis
            kpi_analysis = await self._generate_kpi_analysis(relevant_points, request)
            
            # Generate cross-modal correlations
            cross_modal_correlations = await self._generate_cross_modal_correlations(
                relevant_points, 
                request
            )
            
            # Create comprehensive analytics result
            processing_time = (datetime.utcnow() - start_time).total_seconds()
            
            result = {
                "request_id": request.request_id,
                "insights": [asdict(insight) for insight in all_insights],
                "kpi_analysis": kpi_analysis,
                "cross_modal_correlations": cross_modal_correlations,
                "data_points_analyzed": len(relevant_points),
                "modalities_analyzed": request.modalities,
                "processing_time": processing_time,
                "timestamp": datetime.utcnow().isoformat()
            }
            
            # Cache insights for future use
            self._cache_insights(request.insight_types, all_insights)
            
            logger.info(f"Generated analytics for request {request.request_id} in {processing_time:.2f}s")
            return result
            
        except Exception as e:
            logger.error(f"Failed to generate analytics: {e}")
            raise
    
    async def create_dashboard(self, dashboard: MultimodalDashboard) -> str:
        """Create multimodal analytics dashboard"""
        try:
            # Generate ID if not provided
            if not dashboard.dashboard_id:
                dashboard.dashboard_id = str(uuid.uuid4())
            
            # Store dashboard
            self.dashboards[dashboard.dashboard_id] = dashboard
            
            # Schedule dashboard refresh
            if dashboard.refresh_interval:
                refresh_task = {
                    "type": "dashboard_refresh",
                    "dashboard_id": dashboard.dashboard_id,
                    "next_refresh": datetime.utcnow() + timedelta(seconds=dashboard.refresh_interval)
                }
                await self.analytics_queue.put(refresh_task)
            
            logger.info(f"Created dashboard {dashboard.dashboard_id}: {dashboard.name}")
            return dashboard.dashboard_id
            
        except Exception as e:
            logger.error(f"Failed to create dashboard: {e}")
            raise
    
    async def get_dashboard_data(self, dashboard_id: str) -> Dict[str, Any]:
        """Get real-time dashboard data"""
        try:
            dashboard = self.dashboards.get(dashboard_id)
            
            if not dashboard:
                raise ValueError(f"Dashboard {dashboard_id} not found")
            
            # Collect data based on dashboard configuration
            dashboard_data = {
                "dashboard_id": dashboard_id,
                "name": dashboard.name,
                "description": dashboard.description,
                "widgets": [],
                "last_updated": datetime.utcnow().isoformat()
            }
            
            # Process each widget
            for widget in dashboard.widgets:
                widget_data = await self._process_widget(widget, dashboard)
                dashboard_data["widgets"].append(widget_data)
            
            return dashboard_data
            
        except Exception as e:
            logger.error(f"Failed to get dashboard data: {e}")
            raise
    
    async def _process_analytics_loop(self):
        """Process analytics queue"""
        try:
            while True:
                task = await self.analytics_queue.get()
                await self._process_analytics_task(task)
                
        except Exception as e:
            logger.error(f"Error in analytics processing loop: {e}")
    
    async def _process_analytics_task(self, task: Dict[str, Any]):
        """Process individual analytics task"""
        try:
            task_type = task["type"]
            
            if task_type == "data_point_analysis":
                await self._process_data_point_analysis(task["data_point_id"])
            elif task_type == "insight_generation":
                await self._process_insight_generation(task)
            elif task_type == "dashboard_refresh":
                await self._process_dashboard_refresh(task)
            
        except Exception as e:
            logger.error(f"Failed to process analytics task: {e}")
    
    async def _process_data_point_analysis(self, data_point_id: str):
        """Process individual data point for insights"""
        try:
            data_point = self.data_points.get(data_point_id)
            
            if not data_point:
                return
            
            # Analyze modalities for immediate insights
            immediate_insights = await self._analyze_data_point_modalities(data_point)
            
            # Update data point with insights
            data_point.insights.update(immediate_insights)
            
            # Extract KPI values
            kpi_values = await self._extract_kpi_values(data_point)
            data_point.kpi_values.update(kpi_values)
            
        except Exception as e:
            logger.error(f"Failed to process data point analysis: {e}")
    
    async def _analyze_data_point_modalities(self, data_point: MultimodalDataPoint) -> Dict[str, Any]:
        """Analyze modalities in data point for insights"""
        insights = {}
        
        try:
            # Analyze image modality
            if "image" in data_point.modalities:
                vision_request = type('VisionRequest', (), {
                    'request_id': str(uuid.uuid4()),
                    'task_type': VisionTask.IMAGE_ANALYSIS,
                    'vision_model': VisionModel.OPENAI_VISION,
                    'image_data': data_point.modalities["image"],
                    'context': {"business_analysis": True}
                })()
                
                vision_response = await self.vision_ai.process_vision_request(vision_request)
                
                if vision_response.success:
                    insights["vision_analysis"] = vision_response.results
            
            # Analyze audio modality
            if "audio" in data_point.modalities:
                audio_request = type('AudioRequest', (), {
                    'request_id': str(uuid.uuid4()),
                    'task_type': AudioTask.AUDIO_ANALYSIS,
                    'audio_model': AudioModel.WHISPER_LOCAL,
                    'audio_data': data_point.modalities["audio"],
                    'context': {"business_analysis": True}
                })()
                
                audio_response = await self.audio_ai.process_audio_request(audio_request)
                
                if audio_response.success:
                    insights["audio_analysis"] = audio_response.results
            
            # Cross-modal analysis if multiple modalities
            if len(data_point.modalities) > 1:
                cross_modal_request = type('CrossModalRequest', (), {
                    'request_id': str(uuid.uuid4()),
                    'task_type': CrossModalTask.CONTENT_UNDERSTANDING,
                    'content_data': data_point.modalities,
                    'text_prompt': "Analyze this multimodal content for business insights.",
                    'context': {"business_analysis": True}
                })()
                
                cross_modal_response = await self.cross_modal_ai.process_cross_modal_request(cross_modal_request)
                
                if cross_modal_response.success:
                    insights["cross_modal_analysis"] = {
                        "insights": [asdict(insight) for insight in cross_modal_response.insights],
                        "correlations": [asdict(correlation) for correlation in cross_modal_response.correlations]
                    }
        
        except Exception as e:
            logger.error(f"Failed to analyze data point modalities: {e}")
            insights["analysis_error"] = str(e)
        
        return insights
    
    async def _extract_kpi_values(self, data_point: MultimodalDataPoint) -> Dict[str, float]:
        """Extract KPI values from data point"""
        kpi_values = {}
        
        try:
            # Extract from text modalities
            if "text" in data_point.modalities:
                text_data = data_point.modalities["text"]
                
                # Text-based KPIs
                kpi_values["text_sentiment"] = await self._analyze_sentiment(text_data)
                kpi_values["text_complexity"] = len(text_data.split())
                kpi_values["text_engagement"] = len(text_data.split())  # Simplified
            
            # Extract from analysis insights
            if data_point.insights:
                insights_text = json.dumps(data_point.insights)
                kpi_values["insight_confidence"] = np.mean([
                    insight.get("confidence", 0.5) 
                    for insight in data_point.insights.get("cross_modal_analysis", {}).get("insights", [])
                ])
            
            # Extract from modalities metadata
            for modality, data in data_point.modalities.items():
                if modality == "image":
                    kpi_values[f"{modality}_size"] = len(data) if isinstance(data, (bytes, str)) else 1
                elif modality == "audio":
                    kpi_values[f"{modality}_duration"] = 1.0  # Placeholder - would extract from audio metadata
        
        except Exception as e:
            logger.error(f"Failed to extract KPI values: {e}")
        
        return kpi_values
    
    async def _analyze_sentiment(self, text: str) -> float:
        """Analyze sentiment of text"""
        try:
            # Simple sentiment analysis (in production would use NLP service)
            positive_words = ["good", "great", "excellent", "positive", "success", "amazing", "wonderful"]
            negative_words = ["bad", "terrible", "negative", "failure", "poor", "awful", "horrible"]
            
            text_lower = text.lower()
            positive_count = sum(1 for word in positive_words if word in text_lower)
            negative_count = sum(1 for word in negative_words if word in text_lower)
            
            total_sentiment_words = positive_count + negative_count
            if total_sentiment_words == 0:
                return 0.5  # Neutral
            
            sentiment = (positive_count - negative_count) / total_sentiment_words
            return max(-1.0, min(1.0, sentiment))  # Clamp to [-1, 1]
        
        except Exception as e:
            logger.error(f"Failed to analyze sentiment: {e}")
            return 0.5  # Neutral
    
    def _collect_relevant_data_points(self, request: AnalyticsRequest) -> List[MultimodalDataPoint]:
        """Collect data points relevant to analytics request"""
        try:
            relevant_points = []
            
            # Iterate through time window
            current_time = request.time_window[0]
            
            while current_time <= request.time_window[1]:
                if current_time in self.time_series_data:
                    point_ids = self.time_series_data[current_time]
                    
                    for point_id in point_ids:
                        data_point = self.data_points.get(point_id)
                        
                        if data_point and self._is_data_point_relevant(data_point, request):
                            relevant_points.append(data_point)
                
                # Move to next time unit based on granularity
                if request.granularity == TimeGranularity.MINUTE:
                    current_time += timedelta(minutes=1)
                elif request.granularity == TimeGranularity.HOUR:
                    current_time += timedelta(hours=1)
                elif request.granularity == TimeGranularity.DAY:
                    current_time += timedelta(days=1)
                elif request.granularity == TimeGranularity.WEEK:
                    current_time += timedelta(weeks=1)
                elif request.granularity == TimeGranularity.MONTH:
                    current_time += timedelta(days=30)
                else:
                    current_time += timedelta(hours=1)  # Default to hourly
            
            return relevant_points
        
        except Exception as e:
            logger.error(f"Failed to collect relevant data points: {e}")
            return []
    
    def _is_data_point_relevant(self, data_point: MultimodalDataPoint, request: AnalyticsRequest) -> bool:
        """Check if data point is relevant to request"""
        try:
            # Check modality filter
            if request.modalities:
                modalities_match = any(mod in data_point.modalities for mod in request.modalities)
                if not modalities_match:
                    return False
            
            # Check filters
            for filter_key, filter_value in request.filters.items():
                if filter_key == "tags":
                    if not any(tag in data_point.tags for tag in filter_value):
                        return False
                elif filter_key == "metadata":
                    if not all(data_point.metadata.get(k) == v for k, v in filter_value.items()):
                        return False
            
            return True
        
        except Exception as e:
            logger.error(f"Failed to check data point relevance: {e}")
            return False
    
    async def _generate_insights_by_type(self, insight_type: InsightType, 
                                       data_points: List[MultimodalDataPoint], 
                                       request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate insights by specific type"""
        try:
            if insight_type == InsightType.TREND_ANALYSIS:
                return await self._generate_trend_insights(data_points, request)
            elif insight_type == InsightType.ANOMALY_DETECTION:
                return await self._generate_anomaly_insights(data_points, request)
            elif insight_type == InsightType.CORRELATION_ANALYSIS:
                return await self._generate_correlation_insights(data_points, request)
            elif insight_type == InsightType.PREDICTIVE_INSIGHTS:
                return await self._generate_predictive_insights(data_points, request)
            elif insight_type == InsightType.PERFORMANCE_METRICS:
                return await self._generate_performance_insights(data_points, request)
            elif insight_type == InsightType.CROSS_MODAL_INSIGHTS:
                return await self._generate_cross_modal_insights(data_points, request)
            elif insight_type == InsightType.BUSINESS_INTELLIGENCE:
                return await self._generate_business_intelligence(data_points, request)
            else:
                return []
        
        except Exception as e:
            logger.error(f"Failed to generate insights for type {insight_type}: {e}")
            return []
    
    async def _generate_trend_insights(self, data_points: List[MultimodalDataPoint], 
                                    request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate trend analysis insights"""
        try:
            insights = []
            
            # Sort data points by timestamp
            sorted_points = sorted(data_points, key=lambda x: x.timestamp)
            
            # Analyze trends in KPIs
            for kpi_name in request.kpi_names:
                kpi_values = []
                timestamps = []
                
                for point in sorted_points:
                    if kpi_name in point.kpi_values:
                        kpi_values.append(point.kpi_values[kpi_name])
                        timestamps.append(point.timestamp)
                
                if len(kpi_values) >= 3:  # Need at least 3 points for trend
                    # Simple linear trend analysis
                    trend_slope = self._calculate_trend_slope(kpi_values)
                    trend_direction = "increasing" if trend_slope > 0 else "decreasing"
                    
                    # Create insight
                    insight = BusinessInsight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.TREND_ANALYSIS,
                        title=f"KPI Trend: {kpi_name}",
                        description=f"KPI '{kpi_name}' shows {trend_direction} trend with slope {trend_slope:.3f}",
                        confidence=min(0.9, len(kpi_values) / 10),  # More data = higher confidence
                        impact_level="high" if abs(trend_slope) > 0.1 else "medium",
                        supporting_data={
                            "kpi_name": kpi_name,
                            "trend_slope": trend_slope,
                            "data_points": len(kpi_values),
                            "values": kpi_values[-5:]  # Last 5 values
                        },
                        recommendations=[
                            f"Monitor {kpi_name} trend closely",
                            f"Investigate drivers of {trend_direction} trend"
                        ],
                        time_window=(min(timestamps), max(timestamps)),
                        kpi_impact={kpi_name: trend_slope},
                        modalities_used=[mod for point in sorted_points for mod in point.modalities.keys()],
                        generated_at=datetime.utcnow()
                    )
                    
                    insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate trend insights: {e}")
            return []
    
    async def _generate_anomaly_insights(self, data_points: List[MultimodalDataPoint], 
                                      request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate anomaly detection insights"""
        try:
            insights = []
            
            for kpi_name in request.kpi_names:
                kpi_values = []
                for point in data_points:
                    if kpi_name in point.kpi_values:
                        kpi_values.append(point.kpi_values[kpi_name])
                
                if len(kpi_values) >= 5:  # Need enough data for anomaly detection
                    # Simple statistical anomaly detection
                    mean_val = np.mean(kpi_values)
                    std_val = np.std(kpi_values)
                    
                    anomalies = []
                    for i, value in enumerate(kpi_values):
                        if abs(value - mean_val) > 2 * std_val:  # 2 sigma rule
                            anomalies.append({
                                "index": i,
                                "value": value,
                                "z_score": abs(value - mean_val) / std_val
                            })
                    
                    if anomalies:
                        insight = BusinessInsight(
                            insight_id=str(uuid.uuid4()),
                            insight_type=InsightType.ANOMALY_DETECTION,
                            title=f"Anomaly Detected: {kpi_name}",
                            description=f"Found {len(anomalies)} anomalies in {kpi_name} data",
                            confidence=0.8,
                            impact_level="high" if len(anomalies) > 2 else "medium",
                            supporting_data={
                                "kpi_name": kpi_name,
                                "mean": mean_val,
                                "std": std_val,
                                "anomalies": anomalies,
                                "total_anomalies": len(anomalies)
                            },
                            recommendations=[
                                f"Investigate anomalies in {kpi_name}",
                                "Review data quality and collection process"
                            ],
                            time_window=request.time_window,
                            kpi_impact={kpi_name: -len(anomalies) * 0.1},  # Negative impact
                            modalities_used=[mod for point in data_points for mod in point.modalities.keys()],
                            generated_at=datetime.utcnow()
                        )
                        
                        insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate anomaly insights: {e}")
            return []
    
    async def _generate_correlation_insights(self, data_points: List[MultimodalDataPoint], 
                                         request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate correlation analysis insights"""
        try:
            insights = []
            
            # Collect KPI data
            kpi_data = {}
            for point in data_points:
                for kpi_name, value in point.kpi_values.items():
                    if kpi_name not in kpi_data:
                        kpi_data[kpi_name] = []
                    kpi_data[kpi_name].append(value)
            
            # Calculate correlations between KPI pairs
            if len(kpi_data) >= 2:
                kpi_names = list(kpi_data.keys())
                
                for i in range(len(kpi_names)):
                    for j in range(i + 1, len(kpi_names)):
                        kpi1, kpi2 = kpi_names[i], kpi_names[j]
                        
                        if len(kpi_data[kpi1]) == len(kpi_data[kpi2]):
                            correlation = np.corrcoef(kpi_data[kpi1], kpi_data[kpi2])[0, 1]
                            
                            if abs(correlation) > 0.5:  # Significant correlation
                                insight = BusinessInsight(
                                    insight_id=str(uuid.uuid4()),
                                    insight_type=InsightType.CORRELATION_ANALYSIS,
                                    title=f"Correlation: {kpi1} vs {kpi2}",
                                    description=f"Found {'strong' if abs(correlation) > 0.8 else 'moderate'} correlation of {correlation:.3f} between {kpi1} and {kpi2}",
                                    confidence=0.75,
                                    impact_level="medium",
                                    supporting_data={
                                        "kpi1": kpi1,
                                        "kpi2": kpi2,
                                        "correlation": correlation,
                                        "data_points": len(kpi_data[kpi1])
                                    },
                                    recommendations=[
                                        f"Explore causal relationship between {kpi1} and {kpi2}",
                                        f"Consider joint optimization of correlated KPIs"
                                    ],
                                    time_window=request.time_window,
                                    kpi_impact={kpi1: correlation * 0.1, kpi2: correlation * 0.1},
                                    modalities_used=[mod for point in data_points for mod in point.modalities.keys()],
                                    generated_at=datetime.utcnow()
                                )
                                
                                insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate correlation insights: {e}")
            return []
    
    async def _generate_predictive_insights(self, data_points: List[MultimodalDataPoint], 
                                        request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate predictive insights"""
        try:
            insights = []
            
            # Simple predictive modeling based on trends
            for kpi_name in request.kpi_names:
                kpi_values = []
                timestamps = []
                
                for point in sorted(data_points, key=lambda x: x.timestamp):
                    if kpi_name in point.kpi_values:
                        kpi_values.append(point.kpi_values[kpi_name])
                        timestamps.append(point.timestamp)
                
                if len(kpi_values) >= 5:
                    # Linear prediction
                    trend_slope = self._calculate_trend_slope(kpi_values)
                    last_value = kpi_values[-1]
                    
                    # Predict next period
                    predicted_value = last_value + trend_slope
                    
                    insight = BusinessInsight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.PREDICTIVE_INSIGHTS,
                        title=f"Prediction: {kpi_name}",
                        description=f"Predicted next value for {kpi_name}: {predicted_value:.3f} (trend: {'↑' if trend_slope > 0 else '↓'})",
                        confidence=0.6,  # Lower confidence for predictions
                        impact_level="medium",
                        supporting_data={
                            "kpi_name": kpi_name,
                            "predicted_value": predicted_value,
                            "trend_slope": trend_slope,
                            "last_value": last_value,
                            "confidence": 0.6
                        },
                        recommendations=[
                            f"Monitor {kpi_name} for predicted value",
                            "Prepare actions if prediction materializes"
                        ],
                        time_window=request.time_window,
                        kpi_impact={kpi_name: predicted_value - last_value},
                        modalities_used=[mod for point in data_points for mod in point.modalities.keys()],
                        generated_at=datetime.utcnow()
                    )
                    
                    insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate predictive insights: {e}")
            return []
    
    async def _generate_performance_insights(self, data_points: List[MultimodalDataPoint], 
                                         request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate performance metrics insights"""
        try:
            insights = []
            
            # Calculate performance metrics
            modalities_performance = defaultdict(list)
            
            for point in data_points:
                for modality in point.modalities.keys():
                    modalities_performance[modality].append(point.kpi_values)
            
            for modality, kpi_lists in modalities_performance.items():
                if kpi_lists:
                    avg_sentiment = np.mean([kpi.get("text_sentiment", 0.5) for kpi in kpi_lists])
                    avg_confidence = np.mean([kpi.get("insight_confidence", 0.5) for kpi in kpi_lists])
                    
                    insight = BusinessInsight(
                        insight_id=str(uuid.uuid4()),
                        insight_type=InsightType.PERFORMANCE_METRICS,
                        title=f"Performance: {modality}",
                        description=f"{modality} content shows avg sentiment {avg_sentiment:.3f} and confidence {avg_confidence:.3f}",
                        confidence=0.8,
                        impact_level="medium",
                        supporting_data={
                            "modality": modality,
                            "avg_sentiment": avg_sentiment,
                            "avg_confidence": avg_confidence,
                            "data_points": len(kpi_lists)
                        },
                        recommendations=[
                            f"Optimize {modality} processing for better engagement",
                            f"Focus on improving {modality} content quality"
                        ],
                        time_window=request.time_window,
                        kpi_impact={f"{modality}_performance": avg_confidence},
                        modalities_used=[modality],
                        generated_at=datetime.utcnow()
                    )
                    
                    insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate performance insights: {e}")
            return []
    
    async def _generate_cross_modal_insights(self, data_points: List[MultimodalDataPoint], 
                                           request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate cross-modal insights"""
        try:
            insights = []
            
            # Analyze cross-modal data points
            cross_modal_points = [point for point in data_points if len(point.modalities) > 1]
            
            if cross_modal_points:
                # Calculate cross-modal engagement
                modality_combinations = defaultdict(int)
                
                for point in cross_modal_points:
                    modality_combinations[tuple(sorted(point.modalities.keys()))] += 1
                
                for combo, count in modality_combinations.items():
                    if count >= 3:  # Significant combination
                        insight = BusinessInsight(
                            insight_id=str(uuid.uuid4()),
                            insight_type=InsightType.CROSS_MODAL_INSIGHTS,
                            title=f"Cross-Modal Pattern: {' + '.join(combo)}",
                            description=f"Found {count} instances of {len(combo)}-modal content combination",
                            confidence=0.75,
                            impact_level="medium",
                            supporting_data={
                                "modality_combination": list(combo),
                                "count": count,
                                "percentage": (count / len(cross_modal_points)) * 100
                            },
                            recommendations=[
                                f"Optimize workflow for {len(combo)}-modal content",
                                f"Consider enhancing support for {' + '.join(combo)} combinations"
                            ],
                            time_window=request.time_window,
                            kpi_impact={"cross_modal_engagement": count / len(cross_modal_points)},
                            modalities_used=list(combo),
                            generated_at=datetime.utcnow()
                        )
                        
                        insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate cross-modal insights: {e}")
            return []
    
    async def _generate_business_intelligence(self, data_points: List[MultimodalDataPoint], 
                                           request: AnalyticsRequest) -> List[BusinessInsight]:
        """Generate comprehensive business intelligence insights"""
        try:
            insights = []
            
            # Use AI for comprehensive business intelligence
            business_data = []
            
            for point in data_points:
                business_data.append({
                    "timestamp": point.timestamp.isoformat(),
                    "modalities": list(point.modalities.keys()),
                    "kpi_values": point.kpi_values,
                    "insights": point.insights,
                    "metadata": point.metadata
                })
            
            # Create business intelligence prompt
            bi_prompt = f"""
            Analyze this multimodal business data and provide strategic insights:
            
            Data Summary:
            - Total data points: {len(data_points)}
            - Time window: {request.time_window[0]} to {request.time_window[1]}
            - Modalities analyzed: {request.modalities}
            - KPIs tracked: {request.kpi_names}
            
            Sample data:
            {json.dumps(business_data[:5], indent=2)}
            
            Provide business insights on:
            1. Overall business performance
            2. Key trends and patterns
            3. Strategic recommendations
            4. Risk factors and opportunities
            5. Competitive insights (if applicable)
            
            Format as actionable business intelligence.
            """
            
            # Use AI for business intelligence analysis
            ai_request = type('AIRequest', (), {
                'request_id': str(uuid.uuid4()),
                'model_type': AIModelType.GPT_4_TURBO,
                'prompt': bi_prompt,
                'context': {"business_intelligence": True},
                'metadata': {"task": "business_intelligence"}
            })()
            
            ai_response = await self.advanced_ai.process_request(ai_request)
            
            if ai_response.confidence > 0.6:
                insight = BusinessInsight(
                    insight_id=str(uuid.uuid4()),
                    insight_type=InsightType.BUSINESS_INTELLIGENCE,
                    title="Strategic Business Intelligence",
                    description="Comprehensive AI-generated business insights and recommendations",
                    confidence=ai_response.confidence,
                    impact_level="high",
                    supporting_data={
                        "ai_analysis": ai_response.response,
                        "data_points_analyzed": len(data_points),
                        "model": ai_response.model_type.value
                    },
                    recommendations=[
                        "Review detailed AI analysis for strategic planning",
                        "Implement recommended business improvements",
                        "Monitor identified trends and patterns"
                    ],
                    time_window=request.time_window,
                    kpi_impact={"strategic_impact": ai_response.confidence * 0.5},
                    modalities_used=request.modalities,
                    generated_at=datetime.utcnow()
                )
                
                insights.append(insight)
            
            return insights
        
        except Exception as e:
            logger.error(f"Failed to generate business intelligence: {e}")
            return []
    
    async def _generate_kpi_analysis(self, data_points: List[MultimodalDataPoint], 
                                  request: AnalyticsRequest) -> Dict[str, Any]:
        """Generate comprehensive KPI analysis"""
        try:
            kpi_analysis = {
                "kpis": {},
                "summary": {},
                "trends": {},
                "distributions": {}
            }
            
            # Collect KPI data
            for kpi_name in request.kpi_names:
                kpi_values = []
                
                for point in data_points:
                    if kpi_name in point.kpi_values:
                        kpi_values.append(point.kpi_values[kpi_name])
                
                if kpi_values:
                    kpi_analysis["kpis"][kpi_name] = {
                        "count": len(kpi_values),
                        "mean": np.mean(kpi_values),
                        "median": np.median(kpi_values),
                        "std": np.std(kpi_values),
                        "min": np.min(kpi_values),
                        "max": np.max(kpi_values),
                        "trend": self._calculate_trend_slope(kpi_values),
                        "latest": kpi_values[-1] if kpi_values else None
                    }
            
            # Generate summary
            kpi_analysis["summary"] = {
                "total_data_points": len(data_points),
                "total_kpis_tracked": len(request.kpi_names),
                "modalities_analyzed": request.modalities,
                "time_window": {
                    "start": request.time_window[0].isoformat(),
                    "end": request.time_window[1].isoformat()
                }
            }
            
            return kpi_analysis
        
        except Exception as e:
            logger.error(f"Failed to generate KPI analysis: {e}")
            return {"error": str(e)}
    
    async def _generate_cross_modal_correlations(self, data_points: List[MultimodalDataPoint], 
                                             request: AnalyticsRequest) -> Dict[str, Any]:
        """Generate cross-modal correlation analysis"""
        try:
            correlations = {
                "modality_combinations": {},
                "cross_modal_insights": {},
                "engagement_patterns": {}
            }
            
            # Analyze modality combinations
            modality_combinations = defaultdict(int)
            
            for point in data_points:
                if len(point.modalities) > 1:
                    combo = tuple(sorted(point.modalities.keys()))
                    modality_combinations[combo] += 1
            
            # Calculate correlations between modalities
            for combo, count in modality_combinations.items():
                if len(combo) > 1:
                    correlations["modality_combinations"][" + ".join(combo)] = {
                        "count": count,
                        "percentage": (count / len(data_points)) * 100,
                        "modalities": list(combo)
                    }
            
            return correlations
        
        except Exception as e:
            logger.error(f"Failed to generate cross-modal correlations: {e}")
            return {"error": str(e)}
    
    def _calculate_trend_slope(self, values: List[float]) -> float:
        """Calculate simple linear trend slope"""
        try:
            if len(values) < 2:
                return 0.0
            
            x = np.arange(len(values))
            y = np.array(values)
            
            # Simple linear regression
            slope = np.polyfit(x, y, 1)[0]
            return float(slope)
        
        except Exception as e:
            logger.error(f"Failed to calculate trend slope: {e}")
            return 0.0
    
    def _cache_insights(self, insight_types: List[InsightType], insights: List[BusinessInsight]):
        """Cache insights for future use"""
        try:
            for insight_type in insight_types:
                # Create cache key based on time window
                cache_key = f"{datetime.utcnow().strftime('%Y%m%d_%H')}"
                
                if insight_type not in self.insight_cache:
                    self.insight_cache[insight_type] = {}
                
                self.insight_cache[insight_type][cache_key] = insights[:10]  # Cache top 10 insights
        
        except Exception as e:
            logger.error(f"Failed to cache insights: {e}")
    
    async def _generate_insights_loop(self):
        """Generate insights on schedule"""
        try:
            while True:
                await asyncio.sleep(3600)  # Generate insights every hour
                
                # Create scheduled insight generation task
                insight_task = {
                    "type": "insight_generation",
                    "timestamp": datetime.utcnow(),
                    "time_window": (
                        datetime.utcnow() - timedelta(hours=24),
                        datetime.utcnow()
                    )
                }
                
                await self.analytics_queue.put(insight_task)
        
        except Exception as e:
            logger.error(f"Error in insights generation loop: {e}")
    
    async def _generate_insights_on_schedule(self, time_window: Tuple[datetime, datetime]):
        """Generate insights on schedule"""
        try:
            # Collect recent data points
            relevant_points = []
            
            current_time = time_window[0]
            while current_time <= time_window[1]:
                if current_time in self.time_series_data:
                    point_ids = self.time_series_data[current_time]
                    for point_id in point_ids:
                        data_point = self.data_points.get(point_id)
                        if data_point:
                            relevant_points.append(data_point)
                
                current_time += timedelta(hours=1)
            
            if relevant_points:
                # Generate insights for all types
                request = AnalyticsRequest(
                    request_id=str(uuid.uuid4()),
                    insight_types=list(InsightType),
                    time_window=time_window,
                    granularity=TimeGranularity.HOUR,
                    filters={},
                    kpi_names=["text_sentiment", "insight_confidence", "cross_modal_engagement"],
                    modalities=["text", "image", "audio"],
                    options={},
                    metadata={}
                )
                
                await self.generate_analytics(request)
        
        except Exception as e:
            logger.error(f"Failed to generate insights on schedule: {e}")
    
    async def _update_dashboards_loop(self):
        """Update dashboards on schedule"""
        try:
            while True:
                await asyncio.sleep(300)  # Check for dashboard updates every 5 minutes
                
                # Check for dashboards needing refresh
                current_time = datetime.utcnow()
                
                for dashboard_id, dashboard in self.dashboards.items():
                    if dashboard.refresh_interval:
                        # Check if refresh is needed
                        if not hasattr(dashboard, 'next_refresh'):
                            dashboard.next_refresh = current_time + timedelta(seconds=dashboard.refresh_interval)
                        
                        if current_time >= dashboard.next_refresh:
                            refresh_task = {
                                "type": "dashboard_refresh",
                                "dashboard_id": dashboard_id,
                                "next_refresh": current_time + timedelta(seconds=dashboard.refresh_interval)
                            }
                            
                            await self.analytics_queue.put(refresh_task)
        
        except Exception as e:
            logger.error(f"Error in dashboard updates loop: {e}")
    
    async def _process_widget(self, widget: Dict[str, Any], dashboard: MultimodalDashboard) -> Dict[str, Any]:
        """Process individual dashboard widget"""
        try:
            widget_type = widget.get("type")
            widget_config = widget.get("config", {})
            
            widget_data = {
                "widget_id": widget.get("widget_id", str(uuid.uuid4())),
                "type": widget_type,
                "title": widget.get("title", "Widget"),
                "data": {},
                "last_updated": datetime.utcnow().isoformat()
            }
            
            if widget_type == "kpi_chart":
                # Get KPI data
                kpi_name = widget_config.get("kpi_name")
                if kpi_name:
                    kpi_data = await self._get_kpi_time_series(kpi_name, dashboard.time_filters)
                    widget_data["data"] = kpi_data
            
            elif widget_type == "insight_feed":
                # Get recent insights
                insights_feed = await self._get_recent_insights(10)
                widget_data["data"] = {"insights": insights_feed}
            
            elif widget_type == "modality_distribution":
                # Get modality distribution
                modality_dist = await self._get_modality_distribution(dashboard.time_filters)
                widget_data["data"] = modality_dist
            
            return widget_data
        
        except Exception as e:
            logger.error(f"Failed to process widget: {e}")
            return {
                "widget_id": widget.get("widget_id", "error"),
                "type": widget.get("type", "error"),
                "title": "Widget Error",
                "data": {"error": str(e)},
                "last_updated": datetime.utcnow().isoformat()
            }
    
    async def _get_kpi_time_series(self, kpi_name: str, time_filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get KPI time series data"""
        try:
            time_series = []
            
            # Collect KPI values over time
            for timestamp, point_ids in self.time_series_data.items():
                if len(time_series) >= 100:  # Limit to last 100 points
                    break
                
                kpi_values = []
                for point_id in point_ids:
                    data_point = self.data_points.get(point_id)
                    if data_point and kpi_name in data_point.kpi_values:
                        kpi_values.append(data_point.kpi_values[kpi_name])
                
                if kpi_values:
                    time_series.append({
                        "timestamp": timestamp.isoformat(),
                        "value": np.mean(kpi_values),
                        "count": len(kpi_values)
                    })
            
            return {
                "kpi_name": kpi_name,
                "time_series": time_series,
                "summary": {
                    "avg": np.mean([point["value"] for point in time_series]) if time_series else 0,
                    "count": len(time_series)
                }
            }
        
        except Exception as e:
            logger.error(f"Failed to get KPI time series: {e}")
            return {"error": str(e)}
    
    async def _get_recent_insights(self, limit: int) -> List[Dict[str, Any]]:
        """Get recent insights"""
        try:
            recent_insights = []
            
            for insight_id, insight in list(self.insights.items())[-limit:]:
                recent_insights.append({
                    "insight_id": insight.insight_id,
                    "type": insight.insight_type.value,
                    "title": insight.title,
                    "description": insight.description,
                    "confidence": insight.confidence,
                    "impact_level": insight.impact_level,
                    "generated_at": insight.generated_at.isoformat()
                })
            
            return recent_insights
        
        except Exception as e:
            logger.error(f"Failed to get recent insights: {e}")
            return []
    
    async def _get_modality_distribution(self, time_filters: Dict[str, Any]) -> Dict[str, Any]:
        """Get modality distribution"""
        try:
            distribution = defaultdict(int)
            
            for data_point in self.data_points.values():
                for modality in data_point.modalities.keys():
                    distribution[modality] += 1
            
            return {
                "distribution": dict(distribution),
                "total": sum(distribution.values())
            }
        
        except Exception as e:
            logger.error(f"Failed to get modality distribution: {e}")
            return {"error": str(e)}
    
    async def _process_insight_generation(self, task: Dict[str, Any]):
        """Process scheduled insight generation"""
        try:
            await self._generate_insights_on_schedule(task["time_window"])
        except Exception as e:
            logger.error(f"Failed to process insight generation: {e}")
    
    async def _process_dashboard_refresh(self, task: Dict[str, Any]):
        """Process dashboard refresh"""
        try:
            dashboard_id = task["dashboard_id"]
            dashboard = self.dashboards.get(dashboard_id)
            
            if dashboard:
                # Update next refresh time
                dashboard.next_refresh = task["next_refresh"]
                
                # Trigger widget processing (in real implementation, would push updates to clients)
                logger.info(f"Dashboard {dashboard_id} refreshed at {datetime.utcnow()}")
        
        except Exception as e:
            logger.error(f"Failed to process dashboard refresh: {e}")
    
    async def _cleanup_data_loop(self):
        """Cleanup old data"""
        try:
            while True:
                await asyncio.sleep(86400)  # Cleanup every 24 hours
                
                cutoff_time = datetime.utcnow() - timedelta(days=30)
                
                # Remove old data points
                old_point_ids = []
                for point_id, point in self.data_points.items():
                    if point.timestamp < cutoff_time:
                        old_point_ids.append(point_id)
                
                for point_id in old_point_ids:
                    del self.data_points[point_id]
                
                # Remove old time series data
                old_timestamps = []
                for timestamp in self.time_series_data.keys():
                    if timestamp < cutoff_time:
                        old_timestamps.append(timestamp)
                
                for timestamp in old_timestamps:
                    del self.time_series_data[timestamp]
                
                # Clean insights cache
                cache_cutoff = datetime.utcnow() - timedelta(days=7)
                for insight_type in self.insight_cache:
                    keys_to_remove = []
                    for cache_key in self.insight_cache[insight_type].keys():
                        try:
                            cache_date = datetime.strptime(cache_key.split('_')[0] + '_' + cache_key.split('_')[1][:2], '%Y%m%d_%H')
                            if cache_date < cache_cutoff:
                                keys_to_remove.append(cache_key)
                        except:
                            keys_to_remove.append(cache_key)
                    
                    for key in keys_to_remove:
                        del self.insight_cache[insight_type][key]
                
                if old_point_ids:
                    logger.info(f"Cleaned up {len(old_point_ids)} old data points")
                if old_timestamps:
                    logger.info(f"Cleaned up {len(old_timestamps)} old time series entries")
        
        except Exception as e:
            logger.error(f"Error in data cleanup loop: {e}")
    
    async def _update_metrics_loop(self):
        """Update performance metrics"""
        try:
            while True:
                await asyncio.sleep(300)  # Update every 5 minutes
                
                # Calculate metrics
                current_time = datetime.utcnow()
                
                self.performance_metrics = {
                    "total_data_points": len(self.data_points),
                    "total_insights": len(self.insights),
                    "active_dashboards": len(self.dashboards),
                    "modalities_analyzed": list(set(
                        modality for point in self.data_points.values() for modality in point.modalities.keys()
                    )),
                    "data_points_by_hour": len([ts for ts in self.time_series_data.keys() if (current_time - ts).seconds <= 3600]),
                    "insights_by_type": {
                        insight_type.value: len([ins for ins in self.insights.values() if ins.insight_type == insight_type])
                        for insight_type in InsightType
                    },
                    "cache_sizes": {
                        insight_type.value: len(cache) for insight_type, cache in self.insight_cache.items()
                    },
                    "last_updated": current_time.isoformat()
                }
        
        except Exception as e:
            logger.error(f"Error in metrics update loop: {e}")
    
    def get_service_status(self) -> Dict[str, Any]:
        """Get business intelligence service status"""
        return {
            "status": "running",
            "data_points": len(self.data_points),
            "insights": len(self.insights),
            "dashboards": len(self.dashboards),
            "time_series_entries": len(self.time_series_data),
            "performance_metrics": self.performance_metrics,
            "background_tasks": len(self.background_tasks),
            "timestamp": datetime.utcnow().isoformat()
        }

# Factory function
def create_multi_modal_business_intelligence() -> MultiModalBusinessIntelligence:
    """Create multimodal business intelligence service instance"""
    return MultiModalBusinessIntelligence()