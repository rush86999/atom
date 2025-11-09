#!/usr/bin/env python3
"""
AI-Powered Error Prediction System
Predicts integration failures before they happen using machine learning
"""

import os
import json
import logging
import asyncio
import numpy as np
import pandas as pd
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict
from sklearn.ensemble import RandomForestClassifier, IsolationForest
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, confusion_matrix
import joblib
import httpx
from collections import defaultdict, deque
import time

logger = logging.getLogger(__name__)

@dataclass
class ErrorPrediction:
    """Single error prediction result"""
    integration: str
    service: str
    failure_probability: float
    predicted_failure_type: str
    confidence: float
    time_to_failure: Optional[int]  # minutes
    risk_factors: List[str]
    suggested_actions: List[str]
    timestamp: str
    model_version: str

@dataclass
class SystemHealthPrediction:
    """Overall system health prediction"""
    overall_risk_score: float
    high_risk_integrations: List[str]
    predicted_downtime_minutes: Optional[int]
    system_stability_trend: str
    recommendations: List[str]
    timestamp: str

@dataclass
class PerformanceMetrics:
    """Performance metrics for ML model"""
    prediction_accuracy: float
    false_positive_rate: float
    false_negative_rate: float
    precision: float
    recall: float
    f1_score: float
    model_confidence: float

class AIErrorPredictor:
    """Advanced AI-powered error prediction system"""
    
    def __init__(self, model_dir: str = "models"):
        self.model_dir = model_dir
        os.makedirs(model_dir, exist_ok=True)
        
        # ML Models
        self.failure_predictor: Optional[RandomForestClassifier] = None
        self.anomaly_detector: Optional[IsolationForest] = None
        self.scaler: Optional[StandardScaler] = None
        
        # Data storage
        self.training_data = []
        self.prediction_history = deque(maxlen=1000)
        self.feature_cache = {}
        
        # Model metadata
        self.model_version = "1.0.0"
        self.last_training_time = None
        self.prediction_count = 0
        
        # Configuration
        self.prediction_threshold = 0.7
        self.anomaly_threshold = -0.5
        self.retrain_interval_hours = 24
        
        # Initialize models
        self._initialize_models()
    
    def _initialize_models(self):
        """Initialize ML models"""
        try:
            self.failure_predictor = RandomForestClassifier(
                n_estimators=100,
                max_depth=10,
                random_state=42,
                n_jobs=-1
            )
            
            self.anomaly_detector = IsolationForest(
                contamination=0.1,
                random_state=42,
                n_jobs=-1
            )
            
            self.scaler = StandardScaler()
            
            logger.info("AI Error Predictor models initialized")
            
            # Try to load existing models
            self._load_models()
            
        except Exception as e:
            logger.error(f"Failed to initialize models: {e}")
            self._create_backup_models()
    
    def _load_models(self):
        """Load pre-trained models"""
        try:
            model_files = {
                'failure_predictor': 'failure_predictor.joblib',
                'anomaly_detector': 'anomaly_detector.joblib',
                'scaler': 'scaler.joblib',
                'metadata': 'model_metadata.json'
            }
            
            for model_name, filename in model_files.items():
                filepath = os.path.join(self.model_dir, filename)
                if os.path.exists(filepath):
                    if filename.endswith('.joblib'):
                        model = joblib.load(filepath)
                        if model_name == 'failure_predictor':
                            self.failure_predictor = model
                        elif model_name == 'anomaly_detector':
                            self.anomaly_detector = model
                        elif model_name == 'scaler':
                            self.scaler = model
                    else:
                        with open(filepath, 'r') as f:
                            metadata = json.load(f)
                            self.model_version = metadata.get('version', '1.0.0')
                            self.last_training_time = metadata.get('last_training')
            
            logger.info(f"Loaded AI models version {self.model_version}")
            
        except Exception as e:
            logger.warning(f"Failed to load models: {e}, using new models")
    
    def _save_models(self):
        """Save trained models"""
        try:
            # Save ML models
            joblib.dump(self.failure_predictor, 
                       os.path.join(self.model_dir, 'failure_predictor.joblib'))
            joblib.dump(self.anomaly_detector, 
                       os.path.join(self.model_dir, 'anomaly_detector.joblib'))
            joblib.dump(self.scaler, 
                       os.path.join(self.model_dir, 'scaler.joblib'))
            
            # Save metadata
            metadata = {
                'version': self.model_version,
                'last_training': datetime.now(timezone.utc).isoformat(),
                'prediction_count': self.prediction_count,
                'prediction_threshold': self.prediction_threshold,
                'anomaly_threshold': self.anomaly_threshold
            }
            
            with open(os.path.join(self.model_dir, 'model_metadata.json'), 'w') as f:
                json.dump(metadata, f, indent=2)
            
            logger.info("AI models saved successfully")
            
        except Exception as e:
            logger.error(f"Failed to save models: {e}")
    
    def _create_backup_models(self):
        """Create simple backup models when ML fails"""
        logger.warning("Creating backup rule-based models")
        
        # Simple rule-based predictors
        self.failure_predictor = 'rule_based'
        self.anomaly_detector = 'rule_based'
        self.scaler = None
    
    def collect_training_data(self, integration_data: Dict[str, Any]) -> Dict[str, Any]:
        """Collect and process training data from integration metrics"""
        try:
            features = self._extract_features(integration_data)
            label = integration_data.get('failed', False)
            
            training_sample = {
                'features': features,
                'label': label,
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'integration': integration_data.get('integration'),
                'service': integration_data.get('service')
            }
            
            self.training_data.append(training_sample)
            
            # Limit training data size
            if len(self.training_data) > 10000:
                self.training_data = self.training_data[-8000:]
            
            return training_sample
            
        except Exception as e:
            logger.error(f"Failed to collect training data: {e}")
            return {}
    
    def _extract_features(self, data: Dict[str, Any]) -> List[float]:
        """Extract features from integration data for ML"""
        try:
            features = []
            
            # Performance features
            features.append(float(data.get('response_time', 0)))
            features.append(float(data.get('success_rate', 1.0)))
            features.append(float(data.get('error_rate', 0.0)))
            features.append(float(data.get('timeout_rate', 0.0)))
            
            # Request volume features
            features.append(float(data.get('request_count', 0)))
            features.append(float(data.get('request_rate', 0)))
            features.append(float(data.get('concurrent_requests', 0)))
            
            # Time-based features
            current_hour = datetime.now().hour
            features.append(float(current_hour / 24))  # Normalized hour
            features.append(float(datetime.now().weekday() / 7))  # Normalized day
            
            # Health history features
            features.append(float(data.get('health_score_1h', 1.0)))
            features.append(float(data.get('health_score_24h', 1.0)))
            features.append(float(data.get('health_score_7d', 1.0)))
            
            # Error pattern features
            features.append(float(data.get('consecutive_failures', 0)))
            features.append(float(data.get('error_spike', 0)))
            features.append(float(data.get('latency_variance', 0)))
            
            # Integration-specific features
            features.append(float(data.get('api_version', 1.0)))
            features.append(float(data.get('last_error_minutes', 0)))
            features.append(float(data.get('token_expires_hours', 24)))
            
            return features
            
        except Exception as e:
            logger.error(f"Failed to extract features: {e}")
            return [0.0] * 17  # Return zero features on error
    
    async def train_models(self, force_retrain: bool = False) -> bool:
        """Train ML models with collected data"""
        try:
            # Check if we need to retrain
            if not force_retrain and self.last_training_time:
                last_train = datetime.fromisoformat(self.last_training_time)
                if datetime.now() - last_train < timedelta(hours=self.retrain_interval_hours):
                    return True
            
            if len(self.training_data) < 100:
                logger.warning("Insufficient training data (need >100 samples)")
                return False
            
            logger.info(f"Training AI models with {len(self.training_data)} samples")
            
            # Prepare training data
            X = []
            y = []
            
            for sample in self.training_data:
                X.append(sample['features'])
                y.append(1 if sample['label'] else 0)
            
            X = np.array(X)
            y = np.array(y)
            
            # Split data
            X_train, X_test, y_train, y_test = train_test_split(
                X, y, test_size=0.2, random_state=42, stratify=y
            )
            
            # Scale features
            if self.scaler:
                X_train_scaled = self.scaler.fit_transform(X_train)
                X_test_scaled = self.scaler.transform(X_test)
            else:
                X_train_scaled = X_train
                X_test_scaled = X_test
            
            # Train failure predictor
            if self.failure_predictor != 'rule_based':
                self.failure_predictor.fit(X_train_scaled, y_train)
                
                # Evaluate model
                y_pred = self.failure_predictor.predict(X_test_scaled)
                
                accuracy = np.mean(y_pred == y_test)
                logger.info(f"Failure predictor accuracy: {accuracy:.3f}")
            
            # Train anomaly detector
            if self.anomaly_detector != 'rule_based':
                self.anomaly_detector.fit(X_train_scaled)
                
                anomalies = self.anomaly_detector.predict(X_test_scaled)
                anomaly_rate = np.mean(anomalies == -1)
                logger.info(f"Anomaly detection rate: {anomaly_rate:.3f}")
            
            # Save models
            self._save_models()
            self.last_training_time = datetime.now(timezone.utc).isoformat()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to train models: {e}")
            return False
    
    async def predict_failure(self, integration_data: Dict[str, Any]) -> ErrorPrediction:
        """Predict failure for a specific integration"""
        try:
            start_time = time.time()
            
            # Extract features
            features = self._extract_features(integration_data)
            feature_vector = np.array(features).reshape(1, -1)
            
            # Scale features
            if self.scaler and self.scaler != 'rule_based':
                features_scaled = self.scaler.transform(feature_vector)
            else:
                features_scaled = feature_vector
            
            # Predict failure
            failure_probability = 0.0
            predicted_failure_type = "unknown"
            confidence = 0.0
            
            if self.failure_predictor != 'rule_based':
                # Use ML model
                failure_proba = self.failure_predictor.predict_proba(features_scaled)[0]
                failure_probability = failure_proba[1] if len(failure_proba) > 1 else failure_proba[0]
                
                # Get feature importances for explanation
                importances = self.failure_predictor.feature_importances_
                important_features = np.argsort(importances)[-3:]  # Top 3 features
                
                predicted_failure_type = self._predict_failure_type(integration_data, important_features)
                confidence = np.max(failure_proba)
                
            else:
                # Use rule-based prediction
                failure_probability, predicted_failure_type, confidence = self._rule_based_prediction(integration_data)
            
            # Detect anomalies
            is_anomaly = False
            if self.anomaly_detector != 'rule_based':
                anomaly_score = self.anomaly_detector.decision_function(features_scaled)[0]
                is_anomaly = anomaly_score < self.anomaly_threshold
            
            # Calculate time to failure
            time_to_failure = self._estimate_time_to_failure(integration_data, failure_probability)
            
            # Generate risk factors
            risk_factors = self._identify_risk_factors(integration_data, features, is_anomaly)
            
            # Generate suggested actions
            suggested_actions = self._generate_suggested_actions(
                failure_probability, predicted_failure_type, risk_factors
            )
            
            # Create prediction
            prediction = ErrorPrediction(
                integration=integration_data.get('integration', 'unknown'),
                service=integration_data.get('service', 'unknown'),
                failure_probability=failure_probability,
                predicted_failure_type=predicted_failure_type,
                confidence=confidence,
                time_to_failure=time_to_failure,
                risk_factors=risk_factors,
                suggested_actions=suggested_actions,
                timestamp=datetime.now(timezone.utc).isoformat(),
                model_version=self.model_version
            )
            
            # Store prediction
            self.prediction_history.append({
                'prediction': prediction,
                'features': features,
                'actual_outcome': None,
                'prediction_time': time.time() - start_time
            })
            
            self.prediction_count += 1
            
            return prediction
            
        except Exception as e:
            logger.error(f"Failed to predict failure: {e}")
            return ErrorPrediction(
                integration=integration_data.get('integration', 'unknown'),
                service=integration_data.get('service', 'unknown'),
                failure_probability=0.0,
                predicted_failure_type="unknown",
                confidence=0.0,
                time_to_failure=None,
                risk_factors=["prediction_error"],
                suggested_actions=["check_system_logs"],
                timestamp=datetime.now(timezone.utc).isoformat(),
                model_version=self.model_version
            )
    
    def _rule_based_prediction(self, data: Dict[str, Any]) -> Tuple[float, str, float]:
        """Simple rule-based prediction fallback"""
        failure_prob = 0.0
        failure_type = "none"
        confidence = 0.5
        
        # Check response time
        response_time = float(data.get('response_time', 0))
        if response_time > 5000:  # 5 seconds
            failure_prob += 0.3
            failure_type = "performance"
        elif response_time > 2000:  # 2 seconds
            failure_prob += 0.15
        
        # Check error rate
        error_rate = float(data.get('error_rate', 0))
        if error_rate > 0.5:  # 50% errors
            failure_prob += 0.4
            failure_type = "api_error"
        elif error_rate > 0.1:  # 10% errors
            failure_prob += 0.2
        
        # Check consecutive failures
        consecutive_failures = int(data.get('consecutive_failures', 0))
        if consecutive_failures > 5:
            failure_prob += 0.3
            failure_type = "service_down"
        elif consecutive_failures > 2:
            failure_prob += 0.15
        
        # Check token expiration
        token_expires_hours = float(data.get('token_expires_hours', 24))
        if token_expires_hours < 1:
            failure_prob += 0.2
            failure_type = "auth_expiry"
        elif token_expires_hours < 6:
            failure_prob += 0.1
        
        # Cap probability and adjust confidence
        failure_prob = min(failure_prob, 1.0)
        if failure_prob > 0.7:
            confidence = 0.8
        elif failure_prob > 0.3:
            confidence = 0.6
        
        return failure_prob, failure_type, confidence
    
    def _predict_failure_type(self, data: Dict[str, Any], important_features: np.ndarray) -> str:
        """Predict the type of failure based on important features"""
        feature_names = [
            'response_time', 'success_rate', 'error_rate', 'timeout_rate',
            'request_count', 'request_rate', 'concurrent_requests',
            'hour_of_day', 'day_of_week',
            'health_score_1h', 'health_score_24h', 'health_score_7d',
            'consecutive_failures', 'error_spike', 'latency_variance',
            'api_version', 'last_error_minutes', 'token_expires_hours'
        ]
        
        # Determine failure type based on most important features
        top_features = [feature_names[i] for i in important_features]
        
        if 'response_time' in top_features or 'latency_variance' in top_features:
            return "performance"
        elif 'error_rate' in top_features or 'consecutive_failures' in top_features:
            return "api_error"
        elif 'token_expires_hours' in top_features:
            return "auth_expiry"
        elif 'request_count' in top_features or 'request_rate' in top_features:
            return "rate_limit"
        elif 'health_score_1h' in top_features:
            return "service_degradation"
        else:
            return "unknown"
    
    def _estimate_time_to_failure(self, data: Dict[str, Any], failure_prob: float) -> Optional[int]:
        """Estimate minutes until failure"""
        if failure_prob < 0.5:
            return None
        
        # Base time on failure probability
        base_time = max(10, int((1 - failure_prob) * 60))  # 10-60 minutes
        
        # Adjust based on current trends
        consecutive_failures = int(data.get('consecutive_failures', 0))
        if consecutive_failures > 0:
            base_time = max(5, base_time - (consecutive_failures * 5))
        
        error_rate = float(data.get('error_rate', 0))
        if error_rate > 0.2:
            base_time = max(5, base_time - int(error_rate * 30))
        
        return base_time
    
    def _identify_risk_factors(self, data: Dict[str, Any], features: List[float], is_anomaly: bool) -> List[str]:
        """Identify risk factors for the integration"""
        risk_factors = []
        
        # Performance risks
        if float(data.get('response_time', 0)) > 2000:
            risk_factors.append("high_response_time")
        
        if float(data.get('latency_variance', 0)) > 1000:
            risk_factors.append("unstable_performance")
        
        # Error risks
        if float(data.get('error_rate', 0)) > 0.1:
            risk_factors.append("elevated_error_rate")
        
        if int(data.get('consecutive_failures', 0)) > 2:
            risk_factors.append("consecutive_failures")
        
        # Volume risks
        if float(data.get('request_rate', 0)) > 100:
            risk_factors.append("high_request_volume")
        
        # Authentication risks
        token_hours = float(data.get('token_expires_hours', 24))
        if token_hours < 6:
            risk_factors.append("token_expiring_soon")
        
        # Time-based risks
        current_hour = datetime.now().hour
        if current_hour >= 22 or current_hour <= 6:
            risk_factors.append("off_peak_hours")
        
        # Anomaly risk
        if is_anomaly:
            risk_factors.append("anomalous_behavior")
        
        return risk_factors
    
    def _generate_suggested_actions(self, failure_prob: float, failure_type: str, 
                                 risk_factors: List[str]) -> List[str]:
        """Generate suggested actions based on prediction"""
        actions = []
        
        # High probability actions
        if failure_prob > 0.8:
            actions.extend([
                "immediate_health_check_required",
                "enable_circuit_breaker",
                "notify_oncall_team"
            ])
        
        # Type-specific actions
        if failure_type == "performance":
            actions.extend([
                "scale_up_resources",
                "optimize_database_queries",
                "check_network_latency"
            ])
        elif failure_type == "api_error":
            actions.extend([
                "verify_api_credentials",
                "check_rate_limits",
                "review_api_documentation"
            ])
        elif failure_type == "auth_expiry":
            actions.extend([
                "refresh_authentication_tokens",
                "update_oauth_credentials",
                "verify_token_permissions"
            ])
        elif failure_type == "rate_limit":
            actions.extend([
                "implement_request_throttling",
                "optimize_request_patterns",
                "request_rate_limit_increase"
            ])
        
        # Risk factor specific actions
        if "high_response_time" in risk_factors:
            actions.append("investigate_slow_queries")
        
        if "consecutive_failures" in risk_factors:
            actions.append("check_service_logs")
        
        if "token_expiring_soon" in risk_factors:
            actions.append("schedule_token_refresh")
        
        if "high_request_volume" in risk_factors:
            actions.append("monitor_resource_usage")
        
        return list(set(actions))  # Remove duplicates
    
    async def predict_system_health(self) -> SystemHealthPrediction:
        """Predict overall system health"""
        try:
            # Get recent predictions
            recent_predictions = list(self.prediction_history)[-50:]  # Last 50 predictions
            
            if not recent_predictions:
                return SystemHealthPrediction(
                    overall_risk_score=0.0,
                    high_risk_integrations=[],
                    predicted_downtime_minutes=None,
                    system_stability_trend="stable",
                    recommendations=["insufficient_data"],
                    timestamp=datetime.now(timezone.utc).isoformat()
                )
            
            # Calculate overall risk
            high_risk_count = 0
            high_risk_integrations = []
            total_risk = 0.0
            
            for pred_data in recent_predictions:
                if hasattr(pred_data, 'prediction'):
                    pred = pred_data.prediction
                else:
                    pred = pred_data['prediction']
                
                if pred.failure_probability > 0.7:
                    high_risk_count += 1
                    if pred.integration not in high_risk_integrations:
                        high_risk_integrations.append(pred.integration)
                
                total_risk += pred.failure_probability
            
            overall_risk_score = total_risk / len(recent_predictions)
            
            # Predict downtime
            predicted_downtime = None
            if overall_risk_score > 0.8:
                predicted_downtime = max(15, int(overall_risk_score * 60))  # 15-60 minutes
            
            # Determine trend
            if len(recent_predictions) > 20:
                recent_risk = np.mean([p.prediction.failure_probability if hasattr(p, 'prediction') else p['prediction'].failure_probability 
                                      for p in recent_predictions[-10:]])
                older_risk = np.mean([p.prediction.failure_probability if hasattr(p, 'prediction') else p['prediction'].failure_probability 
                                     for p in recent_predictions[-20:-10]])
                
                if recent_risk > older_risk + 0.1:
                    trend = "degrading"
                elif recent_risk < older_risk - 0.1:
                    trend = "improving"
                else:
                    trend = "stable"
            else:
                trend = "insufficient_data"
            
            # Generate recommendations
            recommendations = []
            if overall_risk_score > 0.7:
                recommendations.append("high_system_risk_detected")
            if high_risk_count > 2:
                recommendations.append("multiple_integrations_at_risk")
            if trend == "degrading":
                recommendations.append("system_health_degrading")
            
            return SystemHealthPrediction(
                overall_risk_score=overall_risk_score,
                high_risk_integrations=high_risk_integrations,
                predicted_downtime_minutes=predicted_downtime,
                system_stability_trend=trend,
                recommendations=recommendations,
                timestamp=datetime.now(timezone.utc).isoformat()
            )
            
        except Exception as e:
            logger.error(f"Failed to predict system health: {e}")
            return SystemHealthPrediction(
                overall_risk_score=0.0,
                high_risk_integrations=[],
                predicted_downtime_minutes=None,
                system_stability_trend="error",
                recommendations=["prediction_error"],
                timestamp=datetime.now(timezone.utc).isoformat()
            )
    
    async def evaluate_model_performance(self) -> PerformanceMetrics:
        """Evaluate current model performance"""
        try:
            # Get predictions with known outcomes
            evaluated_predictions = [
                pred for pred in self.prediction_history 
                if pred['actual_outcome'] is not None
            ]
            
            if len(evaluated_predictions) < 10:
                return PerformanceMetrics(
                    prediction_accuracy=0.0,
                    false_positive_rate=0.0,
                    false_negative_rate=0.0,
                    precision=0.0,
                    recall=0.0,
                    f1_score=0.0,
                    model_confidence=0.0
                )
            
            # Calculate metrics
            predictions = []
            actual_outcomes = []
            
            for pred_data in evaluated_predictions:
                pred = pred_data['prediction']
                predictions.append(1 if pred.failure_probability > self.prediction_threshold else 0)
                actual_outcomes.append(1 if pred_data['actual_outcome'] else 0)
            
            # Calculate confusion matrix
            tp = sum(1 for p, a in zip(predictions, actual_outcomes) if p == 1 and a == 1)
            fp = sum(1 for p, a in zip(predictions, actual_outcomes) if p == 1 and a == 0)
            tn = sum(1 for p, a in zip(predictions, actual_outcomes) if p == 0 and a == 0)
            fn = sum(1 for p, a in zip(predictions, actual_outcomes) if p == 0 and a == 1)
            
            # Calculate metrics
            accuracy = (tp + tn) / len(predictions) if predictions else 0
            false_positive_rate = fp / (fp + tn) if (fp + tn) > 0 else 0
            false_negative_rate = fn / (fn + tp) if (fn + tp) > 0 else 0
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1_score = 2 * (precision * recall) / (precision + recall) if (precision + recall) > 0 else 0
            
            # Calculate model confidence
            confidences = [pred['prediction'].confidence for pred in evaluated_predictions]
            model_confidence = np.mean(confidences) if confidences else 0.0
            
            return PerformanceMetrics(
                prediction_accuracy=accuracy,
                false_positive_rate=false_positive_rate,
                false_negative_rate=false_negative_rate,
                precision=precision,
                recall=recall,
                f1_score=f1_score,
                model_confidence=model_confidence
            )
            
        except Exception as e:
            logger.error(f"Failed to evaluate model performance: {e}")
            return PerformanceMetrics(
                prediction_accuracy=0.0,
                false_positive_rate=0.0,
                false_negative_rate=0.0,
                precision=0.0,
                recall=0.0,
                f1_score=0.0,
                model_confidence=0.0
            )
    
    def record_outcome(self, prediction_id: str, actual_failure: bool):
        """Record actual outcome for model improvement"""
        try:
            # Find prediction by ID (simplified - using latest)
            if self.prediction_history:
                latest_pred = self.prediction_history[-1]
                latest_pred['actual_outcome'] = actual_failure
                
                logger.info(f"Recorded outcome for prediction: {actual_failure}")
        except Exception as e:
            logger.error(f"Failed to record outcome: {e}")
    
    async def get_prediction_statistics(self) -> Dict[str, Any]:
        """Get prediction statistics and model info"""
        try:
            stats = {
                'model_version': self.model_version,
                'last_training_time': self.last_training_time,
                'total_predictions': self.prediction_count,
                'training_data_size': len(self.training_data),
                'prediction_threshold': self.prediction_threshold,
                'anomaly_threshold': self.anomaly_threshold,
                'cache_size': len(self.feature_cache),
                'recent_predictions': len(self.prediction_history)
            }
            
            # Calculate recent prediction accuracy
            recent_outcomes = [
                pred for pred in self.prediction_history[-100:] 
                if pred['actual_outcome'] is not None
            ]
            
            if recent_outcomes:
                correct = sum(1 for pred in recent_outcomes 
                             if pred['prediction'].failure_probability > self.prediction_threshold 
                             == pred['actual_outcome'])
                stats['recent_accuracy'] = correct / len(recent_outcomes)
            else:
                stats['recent_accuracy'] = None
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get prediction statistics: {e}")
            return {}

# Global AI predictor instance
ai_predictor: Optional[AIErrorPredictor] = None

def get_ai_predictor() -> AIErrorPredictor:
    """Get global AI predictor instance"""
    global ai_predictor
    if ai_predictor is None:
        ai_predictor = AIErrorPredictor()
    return ai_predictor

async def initialize_ai_error_prediction():
    """Initialize AI error prediction system"""
    try:
        predictor = get_ai_predictor()
        
        # Train models if we have data
        await predictor.train_models()
        
        logger.info("AI Error Prediction system initialized")
        return True
        
    except Exception as e:
        logger.error(f"Failed to initialize AI Error Prediction: {e}")
        return False