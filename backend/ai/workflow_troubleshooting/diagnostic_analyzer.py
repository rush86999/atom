import asyncio
import json
import logging
import re
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class DiagnosticConfidence(Enum):
    """Confidence levels for diagnostic findings"""

    VERY_HIGH = "very_high"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    VERY_LOW = "very_low"


class DiagnosticPattern(Enum):
    """Patterns for automated issue detection"""

    ANOMALY_DETECTION = "anomaly_detection"
    CORRELATION_ANALYSIS = "correlation_analysis"
    TREND_ANALYSIS = "trend_analysis"
    PATTERN_MATCHING = "pattern_matching"
    ROOT_CAUSE_ANALYSIS = "root_cause_analysis"


@dataclass
class DiagnosticFinding:
    """Represents a diagnostic finding from AI analysis"""

    finding_id: str
    pattern: DiagnosticPattern
    confidence: DiagnosticConfidence
    description: str
    evidence: List[str]
    impact_score: float
    related_issues: List[str]
    suggested_actions: List[str]
    detected_at: datetime = None

    def __post_init__(self):
        if self.detected_at is None:
            self.detected_at = datetime.now()


@dataclass
class WorkflowDiagnostic:
    """Comprehensive diagnostic analysis for a workflow"""

    diagnostic_id: str
    workflow_id: str
    findings: List[DiagnosticFinding]
    overall_health_score: float
    risk_level: str
    recommendations: List[str]
    analysis_timestamp: datetime = None

    def __post_init__(self):
        if self.analysis_timestamp is None:
            self.analysis_timestamp = datetime.now()


class AIDiagnosticAnalyzer:
    """
    AI-Powered Diagnostic Analyzer for Workflow Automation
    Uses machine learning and pattern recognition to identify complex issues
    """

    def __init__(self):
        self.anomaly_detector = IsolationForest(contamination=0.1, random_state=42)
        self.scaler = StandardScaler()
        self.pattern_rules = self._initialize_pattern_rules()
        self.correlation_threshold = 0.7
        self.anomaly_threshold = -0.5

    def _initialize_pattern_rules(self) -> Dict[str, Dict[str, Any]]:
        """Initialize pattern matching rules for common workflow issues"""
        return {
            "cascading_failure": {
                "description": "Cascading failures across multiple workflow steps",
                "patterns": [
                    r"step.*failure.*causes.*step.*failure",
                    r"dependency.*chain.*broken",
                    r"propagating.*error",
                ],
                "severity": "high",
                "confidence_threshold": 0.8,
            },
            "resource_contention": {
                "description": "Resource contention causing performance degradation",
                "patterns": [
                    r"resource.*exhaustion",
                    r"memory.*pressure",
                    r"cpu.*contention",
                    r"concurrent.*access",
                ],
                "severity": "medium",
                "confidence_threshold": 0.7,
            },
            "data_race": {
                "description": "Data race conditions in concurrent workflows",
                "patterns": [
                    r"race.*condition",
                    r"concurrent.*modification",
                    r"inconsistent.*state",
                    r"timing.*issue",
                ],
                "severity": "high",
                "confidence_threshold": 0.8,
            },
            "configuration_drift": {
                "description": "Configuration drift causing unexpected behavior",
                "patterns": [
                    r"configuration.*mismatch",
                    r"env.*var.*different",
                    r"setting.*changed",
                    r"parameter.*drift",
                ],
                "severity": "medium",
                "confidence_threshold": 0.6,
            },
            "circular_dependency": {
                "description": "Circular dependencies causing deadlocks",
                "patterns": [
                    r"circular.*dependency",
                    r"deadlock",
                    r"mutual.*waiting",
                    r"infinite.*loop.*dependency",
                ],
                "severity": "critical",
                "confidence_threshold": 0.9,
            },
        }

    async def analyze_workflow_metrics(
        self, workflow_id: str, metrics_history: List[Dict[str, Any]]
    ) -> List[DiagnosticFinding]:
        """Analyze workflow metrics using AI/ML techniques"""
        findings = []

        if not metrics_history:
            return findings

        # Convert metrics to feature vectors
        features = self._extract_features_from_metrics(metrics_history)

        if len(features) < 10:  # Need sufficient data for analysis
            logger.warning(f"Insufficient metrics data for workflow {workflow_id}")
            return findings

        # Detect anomalies
        anomaly_findings = await self._detect_anomalies(
            workflow_id, features, metrics_history
        )
        findings.extend(anomaly_findings)

        # Analyze trends
        trend_findings = await self._analyze_trends(workflow_id, metrics_history)
        findings.extend(trend_findings)

        # Detect correlations
        correlation_findings = await self._detect_correlations(
            workflow_id, metrics_history
        )
        findings.extend(correlation_findings)

        return findings

    def _extract_features_from_metrics(
        self, metrics_history: List[Dict[str, Any]]
    ) -> np.ndarray:
        """Extract numerical features from metrics history"""
        features = []

        for metrics in metrics_history:
            feature_vector = []

            # Response time features
            if "avg_response_time" in metrics:
                feature_vector.append(float(metrics["avg_response_time"]))
            else:
                feature_vector.append(0.0)

            # Error rate features
            if "error_rate" in metrics:
                feature_vector.append(float(metrics["error_rate"]))
            else:
                feature_vector.append(0.0)

            # Throughput features
            if "throughput" in metrics:
                feature_vector.append(float(metrics["throughput"]))
            else:
                feature_vector.append(0.0)

            # Resource usage features
            if "cpu_usage" in metrics:
                feature_vector.append(float(metrics["cpu_usage"]))
            else:
                feature_vector.append(0.0)

            if "memory_usage" in metrics:
                feature_vector.append(float(metrics["memory_usage"]))
            else:
                feature_vector.append(0.0)

            features.append(feature_vector)

        return np.array(features)

    async def _detect_anomalies(
        self,
        workflow_id: str,
        features: np.ndarray,
        metrics_history: List[Dict[str, Any]],
    ) -> List[DiagnosticFinding]:
        """Detect anomalies in workflow metrics using Isolation Forest"""
        findings = []

        try:
            # Scale features
            scaled_features = self.scaler.fit_transform(features)

            # Fit anomaly detection model
            anomaly_scores = self.anomaly_detector.fit_predict(scaled_features)

            # Identify anomalies
            for i, score in enumerate(anomaly_scores):
                if score == -1:  # Anomaly detected
                    metrics = metrics_history[i]
                    timestamp = metrics.get("timestamp", datetime.now())

                    finding = DiagnosticFinding(
                        finding_id=str(uuid.uuid4()),
                        pattern=DiagnosticPattern.ANOMALY_DETECTION,
                        confidence=DiagnosticConfidence.HIGH,
                        description=f"Anomaly detected in workflow {workflow_id} metrics",
                        evidence=[
                            f"Anomaly score: {score}",
                            f"Metrics at {timestamp}: {json.dumps(metrics, default=str)}",
                        ],
                        impact_score=0.8,
                        related_issues=[
                            "performance_degradation",
                            "unexpected_behavior",
                        ],
                        suggested_actions=[
                            "Review recent workflow configuration changes",
                            "Check for external service disruptions",
                            "Monitor resource utilization patterns",
                            "Implement alerting for similar anomalies",
                        ],
                    )
                    findings.append(finding)

        except Exception as e:
            logger.error(f"Anomaly detection failed for workflow {workflow_id}: {e}")

        return findings

    async def _analyze_trends(
        self, workflow_id: str, metrics_history: List[Dict[str, Any]]
    ) -> List[DiagnosticFinding]:
        """Analyze trends in workflow metrics"""
        findings = []

        if len(metrics_history) < 5:
            return findings

        try:
            # Extract time series data
            response_times = [
                float(m.get("avg_response_time", 0)) for m in metrics_history
            ]
            error_rates = [float(m.get("error_rate", 0)) for m in metrics_history]

            # Calculate trends
            response_trend = self._calculate_trend(response_times)
            error_trend = self._calculate_trend(error_rates)

            # Generate findings based on trends
            if response_trend > 0.1:  # Increasing response times
                finding = DiagnosticFinding(
                    finding_id=str(uuid.uuid4()),
                    pattern=DiagnosticPattern.TREND_ANALYSIS,
                    confidence=DiagnosticConfidence.MEDIUM,
                    description=f"Performance degradation trend detected in workflow {workflow_id}",
                    evidence=[
                        f"Response time trend: +{response_trend:.2%}",
                        f"Current avg response time: {response_times[-1]:.2f}s",
                    ],
                    impact_score=0.6,
                    related_issues=["performance_degradation", "resource_constraints"],
                    suggested_actions=[
                        "Optimize workflow steps with highest response times",
                        "Review database query performance",
                        "Consider scaling resources",
                        "Implement caching strategies",
                    ],
                )
                findings.append(finding)

            if error_trend > 0.05:  # Increasing error rates
                finding = DiagnosticFinding(
                    finding_id=str(uuid.uuid4()),
                    pattern=DiagnosticPattern.TREND_ANALYSIS,
                    confidence=DiagnosticConfidence.HIGH,
                    description=f"Error rate increasing in workflow {workflow_id}",
                    evidence=[
                        f"Error rate trend: +{error_trend:.2%}",
                        f"Current error rate: {error_rates[-1]:.2%}",
                    ],
                    impact_score=0.7,
                    related_issues=["reliability_issues", "external_dependencies"],
                    suggested_actions=[
                        "Investigate recent code or configuration changes",
                        "Check external service health",
                        "Review error logs for patterns",
                        "Implement circuit breakers for external calls",
                    ],
                )
                findings.append(finding)

        except Exception as e:
            logger.error(f"Trend analysis failed for workflow {workflow_id}: {e}")

        return findings

    async def _detect_correlations(
        self, workflow_id: str, metrics_history: List[Dict[str, Any]]
    ) -> List[DiagnosticFinding]:
        """Detect correlations between different metrics"""
        findings = []

        if len(metrics_history) < 10:
            return findings

        try:
            # Extract metric pairs for correlation analysis
            metrics_pairs = [
                ("avg_response_time", "error_rate"),
                ("cpu_usage", "avg_response_time"),
                ("memory_usage", "error_rate"),
            ]

            for metric1, metric2 in metrics_pairs:
                values1 = [float(m.get(metric1, 0)) for m in metrics_history]
                values2 = [float(m.get(metric2, 0)) for m in metrics_history]

                correlation = self._calculate_correlation(values1, values2)

                if abs(correlation) > self.correlation_threshold:
                    finding = DiagnosticFinding(
                        finding_id=str(uuid.uuid4()),
                        pattern=DiagnosticPattern.CORRELATION_ANALYSIS,
                        confidence=DiagnosticConfidence.MEDIUM,
                        description=f"Strong correlation detected between {metric1} and {metric2}",
                        evidence=[
                            f"Correlation coefficient: {correlation:.3f}",
                            f"Correlation strength: {'positive' if correlation > 0 else 'negative'}",
                        ],
                        impact_score=0.5,
                        related_issues=[
                            "performance_patterns",
                            "resource_relationships",
                        ],
                        suggested_actions=[
                            f"Investigate relationship between {metric1} and {metric2}",
                            "Consider optimizing the correlated components",
                            "Monitor both metrics together for early detection",
                            "Document the correlation for future troubleshooting",
                        ],
                    )
                    findings.append(finding)

        except Exception as e:
            logger.error(f"Correlation analysis failed for workflow {workflow_id}: {e}")

        return findings

    def _calculate_trend(self, values: List[float]) -> float:
        """Calculate the trend of a time series (simple linear regression)"""
        if len(values) < 2:
            return 0.0

        x = np.arange(len(values))
        y = np.array(values)

        # Remove zeros to avoid division issues
        if np.all(y == 0):
            return 0.0

        # Calculate slope
        slope = np.polyfit(x, y, 1)[0]

        # Normalize by average value
        avg_value = np.mean(y)
        if avg_value == 0:
            return 0.0

        return slope / avg_value

    def _calculate_correlation(
        self, values1: List[float], values2: List[float]
    ) -> float:
        """Calculate Pearson correlation coefficient"""
        if len(values1) != len(values2) or len(values1) < 2:
            return 0.0

        try:
            correlation = np.corrcoef(values1, values2)[0, 1]
            return correlation if not np.isnan(correlation) else 0.0
        except:
            return 0.0

    async def analyze_error_patterns(
        self, workflow_id: str, error_logs: List[str]
    ) -> List[DiagnosticFinding]:
        """Analyze error logs for patterns using AI techniques"""
        findings = []

        if not error_logs:
            return findings

        # Group errors by type and frequency
        error_patterns = self._extract_error_patterns(error_logs)

        for pattern, count in error_patterns.items():
            if count >= 3:  # Only report patterns with multiple occurrences
                finding = DiagnosticFinding(
                    finding_id=str(uuid.uuid4()),
                    pattern=DiagnosticPattern.PATTERN_MATCHING,
                    confidence=DiagnosticConfidence.HIGH,
                    description=f"Recurring error pattern detected in workflow {workflow_id}",
                    evidence=[
                        f"Pattern: {pattern}",
                        f"Occurrences: {count}",
                        f"Sample errors: {error_logs[:3]}",  # Include first few samples
                    ],
                    impact_score=0.7,
                    related_issues=["reliability_issues", "bug_patterns"],
                    suggested_actions=[
                        "Investigate the root cause of this error pattern",
                        "Implement proper error handling for this scenario",
                        "Add monitoring for this specific error type",
                        "Consider adding retry logic or fallback mechanisms",
                    ],
                )
                findings.append(finding)

        return findings

    def _extract_error_patterns(self, error_logs: List[str]) -> Dict[str, int]:
        """Extract and count error patterns from logs"""
        patterns = {}

        for log in error_logs:
            # Extract error type (simplified pattern matching)
            if "timeout" in log.lower():
                patterns["timeout_errors"] = patterns.get("timeout_errors", 0) + 1
            elif "connection" in log.lower() and "failed" in log.lower():
                patterns["connection_errors"] = patterns.get("connection_errors", 0) + 1
            elif "authentication" in log.lower():
                patterns["authentication_errors"] = (
                    patterns.get("authentication_errors", 0) + 1
                )
            elif "permission" in log.lower():
                patterns["permission_errors"] = patterns.get("permission_errors", 0) + 1
            elif "validation" in log.lower():
                patterns["validation_errors"] = patterns.get("validation_errors", 0) + 1
            elif "not found" in log.lower():
                patterns["not_found_errors"] = patterns.get("not_found_errors", 0) + 1
            else:
                patterns["other_errors"] = patterns.get("other_errors", 0) + 1

        return patterns

    async def perform_root_cause_analysis(
        self,
        workflow_id: str,
        issues: List[Dict[str, Any]],
        metrics_history: List[Dict[str, Any]],
    ) -> List[DiagnosticFinding]:
        """Perform root cause analysis using AI techniques"""
        findings = []

        if not issues:
            return findings

        # Analyze temporal patterns
        temporal_findings = await self._analyze_temporal_patterns(
            workflow_id, issues, metrics_history
        )
        findings.extend(temporal_findings)

        # Analyze dependency chains
        dependency_findings = await self._analyze_dependency_chains(workflow_id, issues)
        findings.extend(dependency_findings)

        return findings

    async def _analyze_temporal_patterns(
        self,
        workflow_id: str,
        issues: List[Dict[str, Any]],
        metrics_history: List[Dict[str, Any]],
    ) -> List[DiagnosticFinding]:
        """Analyze temporal patterns in issue occurrences"""
        findings = []

        try:
            # Group issues by time windows
            hourly_issues = {}
            for issue in issues:
                if "detection_time" in issue:
                    hour = issue["detection_time"].hour
                    hourly_issues[hour] = hourly_issues.get(hour, 0) + 1

            # Find peak hours
            if hourly_issues:
                peak_hour = max(hourly_issues, key=hourly_issues.get)
                peak_count = hourly_issues[peak_hour]

                if peak_count >= 5:  # Significant peak
                    finding = DiagnosticFinding(
                        finding_id=str(uuid.uuid4()),
                        pattern=DiagnosticPattern.ROOT_CAUSE_ANALYSIS,
                        confidence=DiagnosticConfidence.MEDIUM,
                        description=f"Temporal pattern detected: peak issues at hour {peak_hour}",
                        evidence=[
                            f"Issues at hour {peak_hour}: {peak_count}",
                        ],
                        impact_score=0.6,
                        related_issues=["temporal_patterns", "workload_distribution"],
                        suggested_actions=[
                            "Investigate workload distribution across hours",
                            "Consider load balancing or scheduling optimizations",
                            "Monitor resource usage during peak hours",
                            "Implement auto-scaling for peak periods",
                        ],
                    )
                    findings.append(finding)

        except Exception as e:
            logger.error(
                f"Temporal pattern analysis failed for workflow {workflow_id}: {e}"
            )

        return findings

    async def _analyze_dependency_chains(
        self, workflow_id: str, issues: List[Dict[str, Any]]
    ) -> List[DiagnosticFinding]:
        """Analyze dependency chains in workflow issues"""
        findings = []

        try:
            # Simple dependency chain analysis
            # In production, this would analyze actual workflow dependencies
            if len(issues) >= 3:
                finding = DiagnosticFinding(
                    finding_id=str(uuid.uuid4()),
                    pattern=DiagnosticPattern.ROOT_CAUSE_ANALYSIS,
                    confidence=DiagnosticConfidence.LOW,
                    description=f"Multiple related issues detected in workflow {workflow_id}",
                    evidence=[
                        f"Total issues analyzed: {len(issues)}",
                        "Issues may be related through dependency chains",
                    ],
                    impact_score=0.5,
                    related_issues=["dependency_chain", "cascading_failure"],
                    suggested_actions=[
                        "Review workflow dependency graph",
                        "Check for circular dependencies",
                        "Implement circuit breakers for dependent services",
                        "Add monitoring for dependency chains",
                    ],
                )
                findings.append(finding)

        except Exception as e:
            logger.error(
                f"Dependency chain analysis failed for workflow {workflow_id}: {e}"
            )

        return findings

    async def generate_comprehensive_diagnostic(
        self,
        workflow_id: str,
        error_logs: List[str],
        metrics_history: List[Dict[str, Any]],
    ) -> WorkflowDiagnostic:
        """Generate comprehensive diagnostic analysis for a workflow"""
        findings = []

        # Run all analysis methods
        metrics_findings = await self.analyze_workflow_metrics(
            workflow_id, metrics_history
        )
        findings.extend(metrics_findings)

        error_findings = await self.analyze_error_patterns(workflow_id, error_logs)
        findings.extend(error_findings)

        # Calculate overall health score
        health_score = self._calculate_health_score(findings)

        # Determine risk level
        if any(
            f.confidence in [DiagnosticConfidence.VERY_HIGH, DiagnosticConfidence.HIGH]
            for f in findings
        ):
            risk_level = "high"
        elif any(f.confidence == DiagnosticConfidence.MEDIUM for f in findings):
            risk_level = "medium"
        else:
            risk_level = "low"

        # Generate recommendations
        recommendations = self._generate_comprehensive_recommendations(findings)

        diagnostic = WorkflowDiagnostic(
            diagnostic_id=str(uuid.uuid4()),
            workflow_id=workflow_id,
            findings=findings,
            overall_health_score=health_score,
            risk_level=risk_level,
            recommendations=recommendations,
        )

        return diagnostic

    def _calculate_health_score(self, findings: List[DiagnosticFinding]) -> float:
        """Calculate overall health score based on diagnostic findings"""
        if not findings:
            return 100.0

        # Start with perfect score
        base_score = 100.0

        # Deduct points based on findings
        for finding in findings:
            # Higher confidence and impact findings reduce score more
            confidence_multiplier = {
                DiagnosticConfidence.VERY_HIGH: 0.8,
                DiagnosticConfidence.HIGH: 0.6,
                DiagnosticConfidence.MEDIUM: 0.4,
                DiagnosticConfidence.LOW: 0.2,
                DiagnosticConfidence.VERY_LOW: 0.1,
            }.get(finding.confidence, 0.1)

            impact_deduction = finding.impact_score * confidence_multiplier * 20
            base_score -= impact_deduction

        # Ensure score is within bounds
        return max(0.0, min(100.0, base_score))

    def _generate_comprehensive_recommendations(
        self, findings: List[DiagnosticFinding]
    ) -> List[str]:
        """Generate comprehensive recommendations from all findings"""
        recommendations = []

        # Collect all suggested actions
        for finding in findings:
            recommendations.extend(finding.suggested_actions)

        # Add general recommendations
        general_recommendations = [
            "Implement comprehensive monitoring and alerting",
            "Establish regular health check procedures",
            "Document troubleshooting procedures for common issues",
            "Set up automated recovery mechanisms",
            "Conduct regular performance reviews",
        ]

        recommendations.extend(general_recommendations)

        # Remove duplicates while preserving order
        seen = set()
        unique_recommendations = []
        for rec in recommendations:
            if rec not in seen:
                seen.add(rec)
                unique_recommendations.append(rec)

        return unique_recommendations
