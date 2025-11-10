"""
Enhanced Workflow Automation API Integration

This module provides the main API integration for enhanced workflow automation
features including AI-powered intelligence, optimization, monitoring, and troubleshooting.
"""

import logging
import uuid
from datetime import datetime
from typing import Any, Dict, List, Optional

from flask import Blueprint, jsonify, request

from .workflow_intelligence_integration import WorkflowIntelligenceIntegration
from .workflow_monitoring_integration import WorkflowMonitoringIntegration
from .workflow_optimization_integration import WorkflowOptimizationIntegration
from .workflow_troubleshooting_integration import WorkflowTroubleshootingIntegration

logger = logging.getLogger(__name__)


class EnhancedWorkflowAPI:
    """Enhanced Workflow Automation API Integration"""

    def __init__(self):
        self.blueprint = Blueprint("enhanced_workflow_automation", __name__)
        self.intelligence = WorkflowIntelligenceIntegration()
        self.optimization = WorkflowOptimizationIntegration()
        self.monitoring = WorkflowMonitoringIntegration()
        self.troubleshooting = WorkflowTroubleshootingIntegration()

        self._register_routes()

    def _register_routes(self):
        """Register all enhanced workflow automation routes"""

        @self.blueprint.route(
            "/api/workflows/enhanced/intelligence/analyze", methods=["POST"]
        )
        def enhanced_intelligence_analyze():
            """Enhanced AI-powered workflow analysis"""
            return self._handle_enhanced_intelligence_analyze()

        @self.blueprint.route(
            "/api/workflows/enhanced/intelligence/generate", methods=["POST"]
        )
        def enhanced_intelligence_generate():
            """Enhanced AI-powered workflow generation"""
            return self._handle_enhanced_intelligence_generate()

        @self.blueprint.route(
            "/api/workflows/enhanced/optimization/analyze", methods=["POST"]
        )
        def enhanced_optimization_analyze():
            """Enhanced workflow optimization analysis"""
            return self._handle_enhanced_optimization_analyze()

        @self.blueprint.route(
            "/api/workflows/enhanced/optimization/apply", methods=["POST"]
        )
        def enhanced_optimization_apply():
            """Apply enhanced workflow optimizations"""
            return self._handle_enhanced_optimization_apply()

        @self.blueprint.route(
            "/api/workflows/enhanced/monitoring/start", methods=["POST"]
        )
        def enhanced_monitoring_start():
            """Start enhanced workflow monitoring"""
            return self._handle_enhanced_monitoring_start()

        @self.blueprint.route(
            "/api/workflows/enhanced/monitoring/health", methods=["GET"]
        )
        def enhanced_monitoring_health():
            """Get enhanced workflow monitoring health"""
            return self._handle_enhanced_monitoring_health()

        @self.blueprint.route(
            "/api/workflows/enhanced/monitoring/metrics", methods=["GET"]
        )
        def enhanced_monitoring_metrics():
            """Get enhanced workflow monitoring metrics"""
            return self._handle_enhanced_monitoring_metrics()

        @self.blueprint.route(
            "/api/workflows/enhanced/troubleshooting/analyze", methods=["POST"]
        )
        def enhanced_troubleshooting_analyze():
            """Enhanced workflow troubleshooting analysis"""
            return self._handle_enhanced_troubleshooting_analyze()

        @self.blueprint.route(
            "/api/workflows/enhanced/troubleshooting/resolve", methods=["POST"]
        )
        def enhanced_troubleshooting_resolve():
            """Enhanced workflow troubleshooting auto-resolution"""
            return self._handle_enhanced_troubleshooting_resolve()

    def _handle_enhanced_intelligence_analyze(self):
        """Handle enhanced intelligence analysis request"""
        try:
            data = request.get_json()
            user_input = data.get("user_input", "").strip()
            context = data.get("context", {})

            if not user_input:
                return jsonify(
                    {"success": False, "error": "user_input is required"}
                ), 400

            result = self.intelligence.analyze_workflow_request(user_input, context)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced intelligence analysis error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced intelligence analysis failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_intelligence_generate(self):
        """Handle enhanced intelligence generation request"""
        try:
            data = request.get_json()
            user_input = data.get("user_input", "").strip()
            context = data.get("context", {})
            optimization_strategy = data.get("optimization_strategy", "performance")

            if not user_input:
                return jsonify(
                    {"success": False, "error": "user_input is required"}
                ), 400

            result = self.intelligence.generate_optimized_workflow(
                user_input, context, optimization_strategy
            )
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced intelligence generation error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced intelligence generation failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_optimization_analyze(self):
        """Handle enhanced optimization analysis request"""
        try:
            data = request.get_json()
            workflow = data.get("workflow", {})
            strategy = data.get("strategy", "performance")

            if not workflow:
                return jsonify({"success": False, "error": "workflow is required"}), 400

            result = self.optimization.analyze_workflow_performance(workflow, strategy)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced optimization analysis error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced optimization analysis failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_optimization_apply(self):
        """Handle enhanced optimization application request"""
        try:
            data = request.get_json()
            workflow = data.get("workflow", {})
            optimizations = data.get("optimizations", [])

            if not workflow:
                return jsonify({"success": False, "error": "workflow is required"}), 400

            result = self.optimization.apply_optimizations(workflow, optimizations)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced optimization application error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced optimization application failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_monitoring_start(self):
        """Handle enhanced monitoring start request"""
        try:
            data = request.get_json()
            workflow_id = data.get("workflow_id")

            if not workflow_id:
                return jsonify(
                    {"success": False, "error": "workflow_id is required"}
                ), 400

            result = self.monitoring.start_monitoring(workflow_id)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced monitoring start error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced monitoring start failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_monitoring_health(self):
        """Handle enhanced monitoring health request"""
        try:
            workflow_id = request.args.get("workflow_id")

            if not workflow_id:
                return jsonify(
                    {"success": False, "error": "workflow_id is required"}
                ), 400

            result = self.monitoring.get_workflow_health(workflow_id)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced monitoring health error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced monitoring health check failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_monitoring_metrics(self):
        """Handle enhanced monitoring metrics request"""
        try:
            workflow_id = request.args.get("workflow_id")
            metric_type = request.args.get("metric_type", "all")

            if not workflow_id:
                return jsonify(
                    {"success": False, "error": "workflow_id is required"}
                ), 400

            result = self.monitoring.get_workflow_metrics(workflow_id, metric_type)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced monitoring metrics error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced monitoring metrics retrieval failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_troubleshooting_analyze(self):
        """Handle enhanced troubleshooting analysis request"""
        try:
            data = request.get_json()
            workflow_id = data.get("workflow_id")
            error_logs = data.get("error_logs", [])

            if not workflow_id:
                return jsonify(
                    {"success": False, "error": "workflow_id is required"}
                ), 400

            result = self.troubleshooting.analyze_workflow_issues(
                workflow_id, error_logs
            )
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced troubleshooting analysis error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced troubleshooting analysis failed: {str(e)}",
                }
            ), 500

    def _handle_enhanced_troubleshooting_resolve(self):
        """Handle enhanced troubleshooting auto-resolution request"""
        try:
            data = request.get_json()
            workflow_id = data.get("workflow_id")
            issues = data.get("issues", [])

            if not workflow_id:
                return jsonify(
                    {"success": False, "error": "workflow_id is required"}
                ), 400

            result = self.troubleshooting.auto_resolve_issues(workflow_id, issues)
            return jsonify(result)

        except Exception as e:
            logger.error(f"Enhanced troubleshooting resolution error: {str(e)}")
            return jsonify(
                {
                    "success": False,
                    "error": f"Enhanced troubleshooting resolution failed: {str(e)}",
                }
            ), 500

    def get_blueprint(self):
        """Get the Flask blueprint for enhanced workflow automation"""
        return self.blueprint
