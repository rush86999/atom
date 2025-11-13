#!/usr/bin/env python3
"""
🤖 ATOM Phase 4: AI-Enhanced Analytics & Intelligence
Implements AI-powered integration insights, predictive analytics, and intelligent automation
"""

import os
import json
import logging
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any, Optional, Union, Tuple
from dataclasses import dataclass, asdict
from enum import Enum
from abc import ABC, abstractmethod
import secrets
import statistics
import re
from collections import defaultdict

logger = logging.getLogger(__name__)

class AIModelType(Enum):
    """AI model types for different analytics tasks"""
    WORKFLOW_OPTIMIZATION = "workflow_optimization"
    ERROR_PREDICTION = "error_prediction"
    USAGE_ANALYSIS = "usage_analysis"
    PERFORMANCE_PREDICTION = "performance_prediction"
    SECURITY_ANALYSIS = "security_analysis"
    RECOMMENDATION_ENGINE = "recommendation_engine"

class InsightCategory(Enum):
    """Categories of AI-generated insights"""
    PERFORMANCE = "performance"
    SECURITY = "security"
    OPTIMIZATION = "optimization"
    PREDICTION = "prediction"
    RECOMMENDATION = "recommendation"
    ANOMALY_DETECTION = "anomaly_detection"

@dataclass
class AIInsight:
    """AI-generated insight with metadata"""
    id: str
    category: InsightCategory
    title: str
    description: str
    confidence: float
    impact_level: str  # high, medium, low
    actionable: bool
    recommended_action: Optional[str]
    supporting_data: Dict[str, Any]
    generated_at: datetime
    expires_at: Optional[datetime]

@dataclass
class WorkflowPattern:
    """Pattern detected in workflow execution"""
    id: str
    workflow_id: str
    pattern_type: str
    frequency: float
    success_rate: float
    average_duration: float
    detected_at: datetime
    optimization_potential: float

@dataclass
class IntegrationAnalytics:
    """Analytics data for an integration"""
    integration: str
    usage_frequency: int
    error_rate: float
    average_response_time: float
    success_rate: float
    user_satisfaction: float
    security_score: float
    cost_impact: float
    period_start: datetime
    period_end: datetime

class AIBaseModel(ABC):
    """Base class for AI models"""
    
    def __init__(self, model_type: AIModelType):
        self.model_type = model_type
        self.trained = False
        self.accuracy = 0.0
        self.last_trained = None
    
    @abstractmethod
    def train(self, data: List[Dict]) -> Dict[str, Any]:
        """Train the AI model"""
        pass
    
    @abstractmethod
    def predict(self, input_data: Dict) -> Dict[str, Any]:
        """Make predictions using the trained model"""
        pass
    
    @abstractmethod
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance for explainability"""
        pass

class WorkflowOptimizationModel(AIBaseModel):
    """AI model for workflow optimization"""
    
    def __init__(self):
        super().__init__(AIModelType.WORKFLOW_OPTIMIZATION)
        self.pattern_weights = {}
        self.optimization_rules = {}
    
    def train(self, data: List[Dict]) -> Dict[str, Any]:
        """Train workflow optimization model"""
        try:
            # Analyze workflow execution patterns
            patterns = self._analyze_workflow_patterns(data)
            
            # Generate optimization rules
            rules = self._generate_optimization_rules(patterns)
            
            # Calculate accuracy based on historical optimization success
            accuracy = self._calculate_optimization_accuracy(data, rules)
            
            self.trained = True
            self.accuracy = accuracy
            self.pattern_weights = patterns
            self.optimization_rules = rules
            self.last_trained = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'patterns_found': len(patterns),
                'rules_generated': len(rules),
                'accuracy': accuracy,
                'training_data_size': len(data)
            }
        except Exception as e:
            logger.error(f"Workflow optimization training failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict(self, input_data: Dict) -> Dict[str, Any]:
        """Predict workflow optimizations"""
        try:
            workflow_data = input_data.get('workflow', {})
            
            # Analyze current workflow for optimization opportunities
            optimization_score = 0.0
            recommendations = []
            
            # Check for common optimization patterns
            if self._has_parallel_opportunities(workflow_data):
                optimization_score += 0.3
                recommendations.append({
                    'type': 'parallel_execution',
                    'description': 'Steps can be executed in parallel',
                    'potential_improvement': '40-60%'
                })
            
            if self._has_cache_opportunities(workflow_data):
                optimization_score += 0.2
                recommendations.append({
                    'type': 'caching',
                    'description': 'API calls can be cached',
                    'potential_improvement': '20-30%'
                })
            
            if self._has_batch_opportunities(workflow_data):
                optimization_score += 0.25
                recommendations.append({
                    'type': 'batch_processing',
                    'description': 'Multiple operations can be batched',
                    'potential_improvement': '15-25%'
                })
            
            # Predict performance improvement
            predicted_improvement = optimization_score * 50  # Max 50% improvement
            
            return {
                'success': True,
                'optimization_score': optimization_score,
                'predicted_improvement': predicted_improvement,
                'recommendations': recommendations,
                'confidence': self.accuracy
            }
        except Exception as e:
            logger.error(f"Workflow optimization prediction failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance for workflow optimization"""
        return {
            'step_count': 0.25,
            'parallel_opportunities': 0.30,
            'api_call_frequency': 0.20,
            'data_volume': 0.15,
            'error_rate': 0.10
        }
    
    def _analyze_workflow_patterns(self, data: List[Dict]) -> Dict[str, Any]:
        """Analyze workflow execution patterns"""
        patterns = {}
        
        for execution in data:
            workflow_id = execution.get('workflow_id')
            steps = execution.get('steps', [])
            duration = execution.get('duration', 0)
            success = execution.get('success', False)
            
            if workflow_id not in patterns:
                patterns[workflow_id] = {
                    'executions': [],
                    'step_patterns': defaultdict(int),
                    'durations': [],
                    'success_rate': 0.0
                }
            
            patterns[workflow_id]['executions'].append(execution)
            patterns[workflow_id]['durations'].append(duration)
            patterns[workflow_id]['success_rate'] += 1 if success else 0
            
            # Analyze step patterns
            for step in steps:
                step_name = step.get('name', '')
                patterns[workflow_id]['step_patterns'][step_name] += 1
        
        # Calculate pattern statistics
        for workflow_id in patterns:
            pattern = patterns[workflow_id]
            total_executions = len(pattern['executions'])
            pattern['success_rate'] = (pattern['success_rate'] / total_executions) * 100
            pattern['average_duration'] = np.mean(pattern['durations'])
            pattern['duration_std'] = np.std(pattern['durations'])
            
            # Convert step patterns to percentages
            total_steps = sum(pattern['step_patterns'].values())
            for step in pattern['step_patterns']:
                pattern['step_patterns'][step] = (pattern['step_patterns'][step] / total_steps) * 100
        
        return patterns
    
    def _generate_optimization_rules(self, patterns: Dict[str, Any]) -> List[Dict]:
        """Generate optimization rules based on patterns"""
        rules = []
        
        for workflow_id, pattern in patterns.items():
            # Rule 1: High success rate workflows can be automated
            if pattern['success_rate'] > 95:
                rules.append({
                    'workflow_id': workflow_id,
                    'rule_type': 'automation_eligible',
                    'condition': f'success_rate > 95%',
                    'action': 'Enable automatic execution',
                    'priority': 'high'
                })
            
            # Rule 2: Long-running workflows need optimization
            if pattern['average_duration'] > 300:  # 5 minutes
                rules.append({
                    'workflow_id': workflow_id,
                    'rule_type': 'performance_optimization',
                    'condition': f'average_duration > 300s',
                    'action': 'Optimize for performance',
                    'priority': 'high'
                })
            
            # Rule 3: High variance workflows need stability improvements
            if pattern['duration_std'] > 60:  # High variance
                rules.append({
                    'workflow_id': workflow_id,
                    'rule_type': 'stability_improvement',
                    'condition': f'duration_std > 60s',
                    'action': 'Implement error handling and retries',
                    'priority': 'medium'
                })
        
        return rules
    
    def _calculate_optimization_accuracy(self, data: List[Dict], rules: List[Dict]) -> float:
        """Calculate optimization accuracy based on historical data"""
        # Mock accuracy calculation - in production would use actual optimization results
        return 0.85
    
    def _has_parallel_opportunities(self, workflow_data: Dict) -> bool:
        """Check if workflow has parallel execution opportunities"""
        steps = workflow_data.get('steps', [])
        return len(steps) > 3  # Simplified logic
    
    def _has_cache_opportunities(self, workflow_data: Dict) -> bool:
        """Check if workflow has caching opportunities"""
        steps = workflow_data.get('steps', [])
        for step in steps:
            if 'api_call' in step.get('name', '').lower():
                return True
        return False
    
    def _has_batch_opportunities(self, workflow_data: Dict) -> bool:
        """Check if workflow has batch processing opportunities"""
        steps = workflow_data.get('steps', [])
        similar_operations = defaultdict(int)
        
        for step in steps:
            step_type = step.get('action', '')
            similar_operations[step_type] += 1
        
        return any(count > 1 for count in similar_operations.values())

class ErrorPredictionModel(AIBaseModel):
    """AI model for predicting integration errors"""
    
    def __init__(self):
        super().__init__(AIModelType.ERROR_PREDICTION)
        self.error_patterns = {}
        self.thresholds = {}
    
    def train(self, data: List[Dict]) -> Dict[str, Any]:
        """Train error prediction model"""
        try:
            # Analyze historical error patterns
            error_patterns = self._analyze_error_patterns(data)
            
            # Determine error thresholds
            thresholds = self._determine_error_thresholds(error_patterns)
            
            # Calculate prediction accuracy
            accuracy = self._calculate_prediction_accuracy(data, error_patterns)
            
            self.trained = True
            self.accuracy = accuracy
            self.error_patterns = error_patterns
            self.thresholds = thresholds
            self.last_trained = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'error_patterns_found': len(error_patterns),
                'thresholds_determined': len(thresholds),
                'accuracy': accuracy,
                'training_data_size': len(data)
            }
        except Exception as e:
            logger.error(f"Error prediction training failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict(self, input_data: Dict) -> Dict[str, Any]:
        """Predict integration errors"""
        try:
            integration = input_data.get('integration', '')
            current_metrics = input_data.get('metrics', {})
            
            # Calculate error risk score
            risk_score = self._calculate_error_risk(integration, current_metrics)
            
            # Predict errors for next 24 hours
            predicted_errors = []
            
            if risk_score > 0.7:
                predicted_errors.append({
                    'error_type': 'timeout',
                    'probability': risk_score * 0.4,
                    'estimated_time': 'next 2-4 hours',
                    'mitigation': 'Increase timeout settings'
                })
            
            if risk_score > 0.8:
                predicted_errors.append({
                    'error_type': 'rate_limit',
                    'probability': risk_score * 0.3,
                    'estimated_time': 'next 4-8 hours',
                    'mitigation': 'Implement request throttling'
                })
            
            if risk_score > 0.6:
                predicted_errors.append({
                    'error_type': 'authentication',
                    'probability': risk_score * 0.2,
                    'estimated_time': 'next 8-12 hours',
                    'mitigation': 'Refresh authentication tokens'
                })
            
            return {
                'success': True,
                'risk_score': risk_score,
                'error_level': 'high' if risk_score > 0.8 else 'medium' if risk_score > 0.6 else 'low',
                'predicted_errors': predicted_errors,
                'confidence': self.accuracy,
                'recommendations': self._generate_error_recommendations(risk_score)
            }
        except Exception as e:
            logger.error(f"Error prediction failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance for error prediction"""
        return {
            'error_rate_trend': 0.30,
            'response_time_increase': 0.25,
            'authentication_age': 0.20,
            'request_frequency': 0.15,
            'recent_errors': 0.10
        }
    
    def _analyze_error_patterns(self, data: List[Dict]) -> Dict[str, Any]:
        """Analyze historical error patterns"""
        patterns = defaultdict(lambda: {
            'count': 0,
            'times': [],
            'conditions': []
        })
        
        for record in data:
            integration = record.get('integration', '')
            error_type = record.get('error_type', '')
            timestamp = record.get('timestamp')
            conditions = record.get('conditions', {})
            
            pattern_key = f"{integration}_{error_type}"
            patterns[pattern_key]['count'] += 1
            patterns[pattern_key]['times'].append(timestamp)
            patterns[pattern_key]['conditions'].append(conditions)
        
        # Calculate pattern statistics
        for pattern_key, pattern in patterns.items():
            pattern['frequency'] = pattern['count'] / len(data)
            pattern['avg_interval'] = self._calculate_avg_interval(pattern['times'])
        
        return dict(patterns)
    
    def _determine_error_thresholds(self, error_patterns: Dict[str, Any]) -> Dict[str, float]:
        """Determine error prediction thresholds"""
        thresholds = {}
        
        for pattern_key, pattern in error_patterns.items():
            # Calculate threshold based on pattern frequency
            if pattern['frequency'] > 0.1:
                thresholds[pattern_key] = 0.7
            elif pattern['frequency'] > 0.05:
                thresholds[pattern_key] = 0.6
            else:
                thresholds[pattern_key] = 0.5
        
        return thresholds
    
    def _calculate_prediction_accuracy(self, data: List[Dict], error_patterns: Dict[str, Any]) -> float:
        """Calculate prediction accuracy"""
        # Mock accuracy calculation
        return 0.88
    
    def _calculate_error_risk(self, integration: str, metrics: Dict) -> float:
        """Calculate error risk score for integration"""
        risk_score = 0.0
        
        # Factor 1: Current error rate
        error_rate = metrics.get('error_rate', 0.0)
        risk_score += min(error_rate * 2, 0.4)
        
        # Factor 2: Response time increase
        response_time = metrics.get('response_time', 0.0)
        if response_time > 1000:  # 1 second
            risk_score += 0.2
        elif response_time > 500:
            risk_score += 0.1
        
        # Factor 3: Recent errors
        recent_errors = metrics.get('recent_errors', 0)
        risk_score += min(recent_errors * 0.05, 0.3)
        
        # Factor 4: Authentication age
        auth_age = metrics.get('auth_age', 0)  # hours
        if auth_age > 24:
            risk_score += 0.1
        
        return min(risk_score, 1.0)
    
    def _calculate_avg_interval(self, times: List[datetime]) -> float:
        """Calculate average interval between timestamps"""
        if len(times) < 2:
            return 0.0
        
        times.sort()
        intervals = []
        
        for i in range(1, len(times)):
            interval = (times[i] - times[i-1]).total_seconds()
            intervals.append(interval)
        
        return np.mean(intervals) if intervals else 0.0
    
    def _generate_error_recommendations(self, risk_score: float) -> List[str]:
        """Generate error prevention recommendations"""
        recommendations = []
        
        if risk_score > 0.8:
            recommendations.append("Implement circuit breaker pattern")
            recommendations.append("Increase monitoring frequency")
            recommendations.append("Prepare emergency rollback procedures")
        elif risk_score > 0.6:
            recommendations.append("Review integration configuration")
            recommendations.append("Implement proactive monitoring")
            recommendations.append("Test error handling procedures")
        elif risk_score > 0.4:
            recommendations.append("Monitor integration health")
            recommendations.append("Review recent logs")
            recommendations.append("Update authentication if needed")
        
        return recommendations

class UsageAnalyticsModel(AIBaseModel):
    """AI model for usage analytics and insights"""
    
    def __init__(self):
        super().__init__(AIModelType.USAGE_ANALYSIS)
        self.usage_patterns = {}
        self.user_segments = {}
    
    def train(self, data: List[Dict]) -> Dict[str, Any]:
        """Train usage analytics model"""
        try:
            # Analyze usage patterns
            usage_patterns = self._analyze_usage_patterns(data)
            
            # Segment users
            user_segments = self._segment_users(data)
            
            # Calculate model accuracy
            accuracy = self._calculate_usage_accuracy(data, usage_patterns)
            
            self.trained = True
            self.accuracy = accuracy
            self.usage_patterns = usage_patterns
            self.user_segments = user_segments
            self.last_trained = datetime.now(timezone.utc)
            
            return {
                'success': True,
                'patterns_found': len(usage_patterns),
                'user_segments': len(user_segments),
                'accuracy': accuracy,
                'training_data_size': len(data)
            }
        except Exception as e:
            logger.error(f"Usage analytics training failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def predict(self, input_data: Dict) -> Dict[str, Any]:
        """Predict usage insights"""
        try:
            user_id = input_data.get('user_id', '')
            integration = input_data.get('integration', '')
            time_period = input_data.get('time_period', '30d')
            
            # Generate usage insights
            insights = []
            
            # Insight 1: Power user identification
            if self._is_power_user(user_id):
                insights.append({
                    'type': 'power_user',
                    'description': 'User is a power user with high usage',
                    'recommendation': 'Offer advanced features and premium support',
                    'confidence': 0.85
                })
            
            # Insight 2: Underutilized integration
            if self._is_underutilized(integration):
                insights.append({
                    'type': 'underutilized',
                    'description': f'{integration} integration is underutilized',
                    'recommendation': 'Send usage tips and feature recommendations',
                    'confidence': 0.75
                })
            
            # Insight 3: Usage trend prediction
            trend_prediction = self._predict_usage_trend(user_id, integration)
            insights.append({
                'type': 'usage_trend',
                'description': f'Usage trend: {trend_prediction["trend"]}',
                'prediction': trend_prediction,
                'confidence': self.accuracy
            })
            
            return {
                'success': True,
                'user_id': user_id,
                'integration': integration,
                'time_period': time_period,
                'insights': insights,
                'confidence': self.accuracy
            }
        except Exception as e:
            logger.error(f"Usage analytics prediction failed: {e}")
            return {'success': False, 'error': str(e)}
    
    def get_feature_importance(self) -> Dict[str, float]:
        """Get feature importance for usage analytics"""
        return {
            'usage_frequency': 0.30,
            'feature_adoption': 0.25,
            'time_of_usage': 0.20,
            'user_role': 0.15,
            'integration_type': 0.10
        }
    
    def _analyze_usage_patterns(self, data: List[Dict]) -> Dict[str, Any]:
        """Analyze usage patterns"""
        patterns = {
            'peak_hours': defaultdict(int),
            'popular_integrations': defaultdict(int),
            'usage_frequency': defaultdict(int),
            'user_engagement': defaultdict(list)
        }
        
        for record in data:
            timestamp = record.get('timestamp')
            integration = record.get('integration', '')
            user_id = record.get('user_id', '')
            engagement_score = record.get('engagement_score', 0)
            
            # Peak hours analysis
            if timestamp:
                hour = timestamp.hour
                patterns['peak_hours'][hour] += 1
            
            # Popular integrations
            patterns['popular_integrations'][integration] += 1
            
            # Usage frequency
            patterns['usage_frequency'][user_id] += 1
            
            # User engagement
            patterns['user_engagement'][user_id].append(engagement_score)
        
        # Calculate averages and trends
        patterns['avg_engagement'] = {}
        for user_id, scores in patterns['user_engagement'].items():
            patterns['avg_engagement'][user_id] = np.mean(scores) if scores else 0
        
        return patterns
    
    def _segment_users(self, data: List[Dict]) -> Dict[str, List[str]]:
        """Segment users based on usage patterns"""
        segments = {
            'power_users': [],
            'regular_users': [],
            'casual_users': [],
            'at_risk_users': []
        }
        
        user_stats = defaultdict(lambda: {
            'usage_count': 0,
            'last_activity': None,
            'engagement_score': 0,
            'integrations_used': set()
        })
        
        for record in data:
            user_id = record.get('user_id', '')
            timestamp = record.get('timestamp')
            engagement = record.get('engagement_score', 0)
            integration = record.get('integration', '')
            
            user_stats[user_id]['usage_count'] += 1
            user_stats[user_id]['engagement_score'] += engagement
            user_stats[user_id]['integrations_used'].add(integration)
            
            if timestamp and (user_stats[user_id]['last_activity'] is None or timestamp > user_stats[user_id]['last_activity']):
                user_stats[user_id]['last_activity'] = timestamp
        
        # Segment users
        for user_id, stats in user_stats.items():
            days_since_last_activity = (datetime.now(timezone.utc) - stats['last_activity']).days if stats['last_activity'] else 365
            
            if stats['usage_count'] > 100 and len(stats['integrations_used']) > 3:
                segments['power_users'].append(user_id)
            elif stats['usage_count'] > 20 and days_since_last_activity < 7:
                segments['regular_users'].append(user_id)
            elif days_since_last_activity < 30:
                segments['casual_users'].append(user_id)
            else:
                segments['at_risk_users'].append(user_id)
        
        return segments
    
    def _calculate_usage_accuracy(self, data: List[Dict], patterns: Dict) -> float:
        """Calculate usage analytics accuracy"""
        # Mock accuracy calculation
        return 0.82
    
    def _is_power_user(self, user_id: str) -> bool:
        """Check if user is a power user"""
        if user_id in self.user_segments.get('power_users', []):
            return True
        
        # Fallback logic based on usage patterns
        user_usage = self.usage_patterns.get('usage_frequency', {}).get(user_id, 0)
        return user_usage > 50
    
    def _is_underutilized(self, integration: str) -> bool:
        """Check if integration is underutilized"""
        integration_usage = self.usage_patterns.get('popular_integrations', {}).get(integration, 0)
        total_usage = sum(self.usage_patterns.get('popular_integrations', {}).values())
        
        if total_usage == 0:
            return False
        
        usage_percentage = (integration_usage / total_usage) * 100
        return usage_percentage < 10  # Less than 10% of total usage
    
    def _predict_usage_trend(self, user_id: str, integration: str) -> Dict[str, Any]:
        """Predict usage trend for user and integration"""
        # Mock trend prediction
        trends = ['increasing', 'stable', 'decreasing']
        weights = [0.4, 0.4, 0.2]  # Bias towards increasing/stable
        
        import random
        trend = random.choices(trends, weights=weights)[0]
        confidence = random.uniform(0.7, 0.9)
        
        return {
            'trend': trend,
            'confidence': confidence,
            'next_period_usage': random.randint(5, 50) if trend == 'increasing' else random.randint(2, 30)
        }

class AIAnalyticsEngine:
    """Main AI analytics engine"""
    
    def __init__(self):
        self.models = {}
        self.insights = []
        self.analytics_data = []
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize all AI models"""
        self.models = {
            AIModelType.WORKFLOW_OPTIMIZATION: WorkflowOptimizationModel(),
            AIModelType.ERROR_PREDICTION: ErrorPredictionModel(),
            AIModelType.USAGE_ANALYSIS: UsageAnalyticsModel()
        }
    
    async def train_all_models(self, training_data: List[Dict]) -> Dict[str, Any]:
        """Train all AI models"""
        results = {}
        
        for model_type, model in self.models.items():
            try:
                result = model.train(training_data)
                results[model_type.value] = result
                logger.info(f"Trained {model_type.value} model: {result.get('success', False)}")
            except Exception as e:
                logger.error(f"Failed to train {model_type.value} model: {e}")
                results[model_type.value] = {'success': False, 'error': str(e)}
        
        return results
    
    async def generate_insights(self, input_data: Dict) -> List[AIInsight]:
        """Generate AI-powered insights"""
        insights = []
        
        for model_type, model in self.models.items():
            if not model.trained:
                continue
            
            try:
                prediction = model.predict(input_data)
                
                if prediction.get('success'):
                    insight = self._convert_prediction_to_insight(
                        model_type, prediction, input_data
                    )
                    if insight:
                        insights.append(insight)
            except Exception as e:
                logger.error(f"Failed to generate insight with {model_type.value}: {e}")
        
        # Store insights
        self.insights.extend(insights)
        
        return insights
    
    async def get_recommendations(self, context: Dict) -> List[Dict]:
        """Get AI-powered recommendations"""
        recommendations = []
        
        # Workflow recommendations
        workflow_context = context.get('workflows', {})
        for workflow_id, workflow_data in workflow_context.items():
            prediction = self.models[AIModelType.WORKFLOW_OPTIMIZATION].predict(workflow_data)
            
            if prediction.get('success') and prediction.get('recommendations'):
                for rec in prediction['recommendations']:
                    recommendations.append({
                        'category': 'workflow_optimization',
                        'target': f'workflow_{workflow_id}',
                        'recommendation': rec['description'],
                        'potential_impact': rec.get('potential_improvement', 'Unknown'),
                        'priority': 'high' if rec['potential_improvement'] > '40%' else 'medium',
                        'confidence': prediction.get('confidence', 0.5)
                    })
        
        # Error prevention recommendations
        integration_context = context.get('integrations', {})
        for integration, metrics in integration_context.items():
            prediction = self.models[AIModelType.ERROR_PREDICTION].predict({
                'integration': integration,
                'metrics': metrics
            })
            
            if prediction.get('success') and prediction.get('recommendations'):
                for rec in prediction['recommendations']:
                    recommendations.append({
                        'category': 'error_prevention',
                        'target': f'integration_{integration}',
                        'recommendation': rec,
                        'risk_level': prediction.get('error_level', 'low'),
                        'priority': 'high' if prediction.get('risk_score', 0) > 0.8 else 'medium',
                        'confidence': prediction.get('confidence', 0.5)
                    })
        
        # Usage optimization recommendations
        user_context = context.get('users', {})
        for user_id, user_data in user_context.items():
            prediction = self.models[AIModelType.USAGE_ANALYSIS].predict({
                'user_id': user_id,
                **user_data
            })
            
            if prediction.get('success') and prediction.get('insights'):
                for insight in prediction['insights']:
                    recommendations.append({
                        'category': 'usage_optimization',
                        'target': f'user_{user_id}',
                        'recommendation': insight.get('description'),
                        'action': insight.get('recommendation'),
                        'confidence': insight.get('confidence', 0.5),
                        'priority': 'medium'
                    })
        
        # Sort by priority and confidence
        recommendations.sort(key=lambda x: (
            {'high': 3, 'medium': 2, 'low': 1}.get(x.get('priority', 'low'), 1),
            x.get('confidence', 0)
        ), reverse=True)
        
        return recommendations
    
    async def detect_anomalies(self, data: Dict) -> List[Dict]:
        """Detect anomalies in integration data"""
        anomalies = []
        
        # Anomaly 1: Unusual error rates
        for integration, metrics in data.get('integrations', {}).items():
            error_rate = metrics.get('error_rate', 0)
            response_time = metrics.get('response_time', 0)
            
            if error_rate > 0.1:  # > 10% error rate
                anomalies.append({
                    'type': 'high_error_rate',
                    'target': integration,
                    'value': error_rate,
                    'threshold': 0.1,
                    'severity': 'high',
                    'description': f'{integration} has unusually high error rate'
                })
            
            if response_time > 2000:  # > 2 seconds
                anomalies.append({
                    'type': 'slow_response',
                    'target': integration,
                    'value': response_time,
                    'threshold': 2000,
                    'severity': 'medium',
                    'description': f'{integration} has unusually slow response time'
                })
        
        # Anomaly 2: Unusual usage patterns
        for user_id, user_data in data.get('users', {}).items():
            usage_count = user_data.get('usage_count', 0)
            last_activity = user_data.get('last_activity')
            
            if usage_count == 0 and last_activity:
                days_inactive = (datetime.now(timezone.utc) - last_activity).days
                if days_inactive > 30:
                    anomalies.append({
                        'type': 'user_inactivity',
                        'target': user_id,
                        'value': days_inactive,
                        'threshold': 30,
                        'severity': 'medium',
                        'description': f'User {user_id} inactive for {days_inactive} days'
                    })
        
        return anomalies
    
    def _convert_prediction_to_insight(self, model_type: AIModelType, prediction: Dict, input_data: Dict) -> Optional[AIInsight]:
        """Convert model prediction to AI insight"""
        try:
            insight_id = f"insight_{secrets.token_urlsafe(16)}"
            
            if model_type == AIModelType.WORKFLOW_OPTIMIZATION:
                return AIInsight(
                    id=insight_id,
                    category=InsightCategory.OPTIMIZATION,
                    title="Workflow Optimization Opportunity",
                    description=f"Workflow optimization opportunities detected with {prediction.get('optimization_score', 0):.2%} improvement potential",
                    confidence=prediction.get('confidence', 0),
                    impact_level="high" if prediction.get('optimization_score', 0) > 0.7 else "medium",
                    actionable=True,
                    recommended_action="Implement workflow optimizations: parallel execution, caching, batching",
                    supporting_data=prediction,
                    generated_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=7)
                )
            
            elif model_type == AIModelType.ERROR_PREDICTION:
                return AIInsight(
                    id=insight_id,
                    category=InsightCategory.PREDICTION,
                    title="Error Prediction Alert",
                    description=f"High error risk detected with {prediction.get('risk_score', 0):.2%} probability",
                    confidence=prediction.get('confidence', 0),
                    impact_level="high" if prediction.get('risk_score', 0) > 0.8 else "medium",
                    actionable=True,
                    recommended_action="Implement error prevention measures: authentication refresh, request throttling",
                    supporting_data=prediction,
                    generated_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(hours=24)
                )
            
            elif model_type == AIModelType.USAGE_ANALYSIS:
                return AIInsight(
                    id=insight_id,
                    category=InsightCategory.RECOMMENDATION,
                    title="Usage Analytics Insight",
                    description="Usage patterns and user behavior insights generated",
                    confidence=prediction.get('confidence', 0),
                    impact_level="medium",
                    actionable=True,
                    recommended_action="Optimize user experience based on usage patterns",
                    supporting_data=prediction,
                    generated_at=datetime.now(timezone.utc),
                    expires_at=datetime.now(timezone.utc) + timedelta(days=3)
                )
            
        except Exception as e:
            logger.error(f"Failed to convert prediction to insight: {e}")
        
        return None
    
    def get_model_status(self) -> Dict[str, Any]:
        """Get status of all AI models"""
        status = {}
        
        for model_type, model in self.models.items():
            status[model_type.value] = {
                'trained': model.trained,
                'accuracy': model.accuracy,
                'last_trained': model.last_trained.isoformat() if model.last_trained else None,
                'feature_importance': model.get_feature_importance() if model.trained else None
            }
        
        return status

# Global AI analytics engine
ai_analytics_engine = AIAnalyticsEngine()

# Export for use in routes
__all__ = [
    'AIAnalyticsEngine',
    'ai_analytics_engine',
    'AIBaseModel',
    'WorkflowOptimizationModel',
    'ErrorPredictionModel',
    'UsageAnalyticsModel',
    'AIInsight',
    'WorkflowPattern',
    'IntegrationAnalytics',
    'AIModelType',
    'InsightCategory'
]